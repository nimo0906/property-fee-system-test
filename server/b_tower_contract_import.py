#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rental contract import helpers for charge objects."""

import re

from server.basic_import import _normalize_payment_cycle, _normalize_water_rate_type
from server.db import h, m
from server.import_parser import normalize_date
from server.import_views import _safe_float, _safe_int

RENTAL_CONTRACT_FIELDS = {
    "building": ["楼栋", "楼座", "项目", "building"],
    "unit": ["单元", "座", "单元/座", "unit"],
    "room_number": ["房号", "房间号", "铺位号/房号", "房号/铺位", "room_number"],
    "floor": ["楼层", "floor", "层"],
    "category": ["房间类型", "类别", "房屋类型", "category"],
    "area": ["面积", "面积㎡", "建筑面积", "合同面积", "area"],
    "tenant_name": ["租户", "租户姓名", "承租人", "客户名称", "tenant_name"],
    "tenant_phone": ["租户电话", "承租人电话", "联系电话", "手机号", "phone"],
    "owner_name": ["业主", "业主姓名", "产权人", "owner_name"],
    "owner_phone": ["业主电话", "owner_phone"],
    "custom_rate": ["物业费单价", "单价", "租金单价", "房租单价", "custom_rate"],
    "payment_cycle": ["缴费周期", "付款周期", "收费周期", "交租方式", "payment_cycle"],
    "contract_start": ["合同开始日期", "合同起始日期", "起租日期", "开始日期", "租赁开始日期"],
    "contract_end": ["合同结束日期", "合同到期日期", "结束日期", "租赁结束日期", "合同截止日期"],
    "water_rate_type": ["水费标准", "水费档位", "water_rate_type"],
    "notes": ["备注", "说明", "notes"],
}


def looks_like_b_tower_contract(headers, rows):
    text = " ".join(str(x or "") for x in headers)
    mapped = _map_headers(headers)
    has_contract = "contract_start" in mapped or "contract_end" in mapped
    has_tenant = "tenant_name" in mapped or "tenant_phone" in mapped
    has_room = "room_number" in mapped
    has_basic_owner = "owner_name" in mapped or "owner_phone" in mapped
    has_basic_category = "category" in mapped or "area" in mapped
    if has_basic_owner and has_basic_category:
        return False
    return bool(has_room and has_contract and has_tenant)


def parse_b_tower_contract_rows(headers, data_rows):
    mapping = _map_headers(headers)
    parsed = []
    for row_no, row in enumerate(data_rows, start=1):
        def val(key):
            idx = mapping.get(key)
            return str(row[idx] or "").strip() if idx is not None and idx < len(row) else ""
        room_number = val("room_number")
        building = val("building") or "默认项目"
        unit = val("unit") or "默认分区"
        contract_start = normalize_date(val("contract_start"))
        contract_end = normalize_date(val("contract_end"))
        payment_cycle_raw = val("payment_cycle")
        payment_cycle = _normalize_payment_cycle(payment_cycle_raw)
        area = _safe_float(val("area"), 0)
        custom_rate_raw = val("custom_rate")
        custom_rate = _safe_float(custom_rate_raw, None) if custom_rate_raw else None
        item = {
            "row_no": row_no,
            "building": building,
            "unit": unit,
            "room_number": room_number,
            "floor": _safe_int(val("floor"), _infer_floor(room_number)),
            "category": val("category") or "出租",
            "area": area,
            "tenant_name": val("tenant_name"),
            "tenant_phone": val("tenant_phone"),
            "owner_name": val("owner_name"),
            "owner_phone": val("owner_phone"),
            "custom_rate": custom_rate,
            "payment_cycle": payment_cycle,
            "contract_start": contract_start,
            "contract_end": contract_end,
            "water_rate_type": _normalize_water_rate_type(val("water_rate_type")),
            "notes": val("notes"),
            "errors": [],
        }
        item["errors"] = _validate_row(item, val("contract_start"), val("contract_end"), payment_cycle_raw, custom_rate_raw)
        if any(str(item.get(k) or "").strip() for k in ("room_number", "tenant_name", "owner_name", "contract_start", "contract_end")):
            parsed.append(item)
    return parsed


def import_b_tower_contract_rows(db, rows, allow_create=False):
    result = {
        "imported_rooms": 0, "updated_rooms": 0, "imported_owners": 0, "skipped": 0,
        "errors": [], "invalid_contracts": [], "skip_examples": [], "changed_rooms": [], "problem_rows": [],
    }
    for row in rows:
        if row.get("errors"):
            _skip(result, row, "；".join(row["errors"]))
            continue
        owner_id = None
        owner_name = row["owner_name"] or row["tenant_name"]
        owner_phone = row["owner_phone"] or row["tenant_phone"]
        if owner_name:
            owner = db.execute("SELECT id,phone FROM owners WHERE name=? LIMIT 1", (owner_name,)).fetchone()
            if owner:
                owner_id = owner["id"]
                if owner_phone and not owner["phone"]:
                    db.execute("UPDATE owners SET phone=? WHERE id=?", (owner_phone, owner_id))
            else:
                cur = db.execute("INSERT INTO owners(name,phone) VALUES(?,?)", (owner_name, owner_phone))
                owner_id = cur.lastrowid
                result["imported_owners"] += 1
        room = db.execute(
            "SELECT * FROM rooms WHERE building=? AND room_number=? LIMIT 1",
            (row["building"], row["room_number"]),
        ).fetchone()
        if not room and not allow_create:
            _skip(result, row, "系统中不存在该收费对象，默认不自动新建")
            continue
        if room:
            db.execute(
                """UPDATE rooms SET unit=?,floor=?,category=?,area=?,owner_id=COALESCE(?,owner_id),
                   tenant_name=COALESCE(NULLIF(?,''),tenant_name),tenant_phone=COALESCE(NULLIF(?,''),tenant_phone),
                   custom_rate=COALESCE(?,custom_rate),payment_cycle=COALESCE(NULLIF(?,''),payment_cycle),
                   contract_start=COALESCE(NULLIF(?,''),contract_start),contract_end=COALESCE(NULLIF(?,''),contract_end),
                   water_rate_type=COALESCE(NULLIF(?,''),water_rate_type),notes=? WHERE id=?""",
                (row["unit"], row["floor"], row["category"], row["area"] or room["area"], owner_id,
                 row["tenant_name"], row["tenant_phone"], row["custom_rate"], row["payment_cycle"],
                 row["contract_start"], row["contract_end"], row["water_rate_type"], row["notes"], room["id"]),
            )
            room_id = room["id"]
            result["updated_rooms"] += 1
            action = "更新"
        else:
            cur = db.execute(
                """INSERT INTO rooms(building,unit,room_number,floor,category,area,owner_id,tenant_name,tenant_phone,
                   custom_rate,payment_cycle,contract_start,contract_end,water_rate_type,notes)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (row["building"], row["unit"], row["room_number"], row["floor"], row["category"], row["area"], owner_id,
                 row["tenant_name"], row["tenant_phone"], row["custom_rate"], row["payment_cycle"],
                 row["contract_start"], row["contract_end"], row["water_rate_type"], row["notes"]),
            )
            room_id = cur.lastrowid
            result["imported_rooms"] += 1
            action = "新增"
        result["changed_rooms"].append({**row, "room_id": room_id, "action": action, "owner_name": owner_name, "owner_phone": owner_phone})
    return result


def render_b_tower_contract_preview(handler, filename, token, rows, allow_create=False):
    def inp(i, key, value, typ="text", step=""):
        step_attr = f' step="{h(step)}"' if step else ""
        return f'<input class="form-control form-control-sm" type="{typ}"{step_attr} name="{key}_{i}" value="{h(value)}">'
    def cycle_options(value):
        labels = [("monthly", "月付"), ("quarterly", "季付"), ("semiannual", "半年付"), ("yearly", "年付")]
        return "".join(f'<option value="{k}" {"selected" if k == value else ""}>{label}</option>' for k, label in labels)
    body = "".join(f'''<tr>
        <td><input class="form-check-input" type="checkbox" name="include_{i}" value="1" checked><input type="hidden" name="row_no_{i}" value="{h(r['row_no'])}"><div class="small text-muted">Excel {h(r['row_no'])}</div></td>
        <td>{inp(i,'building',r['building'])}</td><td>{inp(i,'unit',r['unit'])}</td><td>{inp(i,'room_number',r['room_number'])}</td>
        <td>{inp(i,'tenant_name',r['tenant_name'])}</td><td>{inp(i,'tenant_phone',r['tenant_phone'])}</td>
        <td>{inp(i,'area',r['area'],'number','0.01')}<div class="small text-muted">㎡</div></td>
        <td>{inp(i,'custom_rate',r['custom_rate'] if r['custom_rate'] is not None else '','number','0.01')}</td>
        <td><select class="form-select form-select-sm" name="payment_cycle_{i}">{cycle_options(r['payment_cycle'])}</select></td>
        <td>{inp(i,'contract_start',r['contract_start'],'date')}</td><td>{inp(i,'contract_end',r['contract_end'],'date')}</td>
        <td><select class="form-select form-select-sm" name="water_rate_type_{i}"><option value="非居民" {"selected" if r['water_rate_type']!='特行' else ""}>非居民</option><option value="特行" {"selected" if r['water_rate_type']=='特行' else ""}>特行</option></select></td>
        <td>{inp(i,'notes',r['notes'])}</td>
        <td>{'<span class="badge status-success">可导入</span>' if not r['errors'] else '<span class="badge bg-warning text-dark">需核对</span><div class="small text-danger">' + h('；'.join(r['errors'])) + '</div>'}</td>
        </tr>''' for i, r in enumerate(rows[:200])) or '<tr><td colspan="14" class="text-center text-muted py-4">未识别到出租合同</td></tr>'
    checked = "checked" if allow_create else ""
    disabled = "disabled" if not rows else ""
    handler._html(handler._page("出租合同导入预览", f'''
    <div class="alert alert-warning"><i class="bi bi-building"></i> 出租合同导入预览：默认只更新已有收费对象；如需新建缺失房间，请勾选下方选项。</div>
    <div class="card import-review-card">
      <div class="card-header d-flex justify-content-between align-items-center"><span>可编辑核对表 · {h(filename)} · {len(rows)} 条</span><a class="btn btn-sm btn-outline-secondary" href="/import?data_type=b_tower_contracts">重新上传</a></div>
      <form method="POST" action="/import/upload">
        <input type="hidden" name="mode" value="confirm_b_tower_contracts"><input type="hidden" name="data_type" value="b_tower_contracts"><input type="hidden" name="filename" value="{h(filename)}"><input type="hidden" name="row_count" value="{len(rows[:200])}">
        <div class="card-body py-2"><label class="form-check"><input class="form-check-input" type="checkbox" name="allow_create_rooms" value="1" {checked}> 允许自动新建系统中不存在的收费对象</label></div>
        <div class="table-responsive import-sticky-scroll"><table class="table table-sm table-hover align-middle mb-0 import-edit-table"><thead><tr><th>导入</th><th>楼栋</th><th>单元</th><th>房号</th><th>租户</th><th>电话</th><th>面积</th><th>物业费单价</th><th>缴费周期</th><th>合同开始</th><th>合同结束</th><th>水费标准</th><th>备注</th><th>状态</th></tr></thead><tbody>{body}</tbody></table></div>
        <div class="card-body text-end"><button class="btn btn-success" {disabled}>确认导入出租合同</button></div>
      </form>
    </div>''', "import"))


def rows_from_b_tower_form(d):
    count = _safe_int(_get(d, "row_count"), 0)
    rows = []
    for i in range(count):
        if _get(d, f"include_{i}") != "1":
            continue
        row = {
            "row_no": _safe_int(_get(d, f"row_no_{i}"), i + 1),
            "building": _get(d, f"building_{i}") or "默认项目",
            "unit": _get(d, f"unit_{i}") or "默认分区",
            "room_number": _get(d, f"room_number_{i}"),
            "floor": _infer_floor(_get(d, f"room_number_{i}")),
            "category": "出租",
            "area": _safe_float(_get(d, f"area_{i}"), 0),
            "tenant_name": _get(d, f"tenant_name_{i}"),
            "tenant_phone": _get(d, f"tenant_phone_{i}"),
            "owner_name": "",
            "owner_phone": "",
            "custom_rate": _safe_float(_get(d, f"custom_rate_{i}"), None) if _get(d, f"custom_rate_{i}") else None,
            "payment_cycle": _get(d, f"payment_cycle_{i}"),
            "contract_start": _get(d, f"contract_start_{i}"),
            "contract_end": _get(d, f"contract_end_{i}"),
            "water_rate_type": _get(d, f"water_rate_type_{i}") or "非居民",
            "notes": _get(d, f"notes_{i}"),
            "errors": [],
        }
        row["errors"] = _validate_row(row, row["contract_start"], row["contract_end"], row["payment_cycle"], row["custom_rate"])
        rows.append(row)
    return rows


def _map_headers(headers):
    normalized = {_norm(h): i for i, h in enumerate(headers)}
    result = {}
    for key, names in RENTAL_CONTRACT_FIELDS.items():
        for name in names:
            idx = normalized.get(_norm(name))
            if idx is not None:
                result[key] = idx
                break
    return result


def _norm(value):
    return str(value or "").strip().replace("\n", "").replace("\r", "").lower()


def _infer_floor(room_number):
    text = str(room_number or "")
    match = re.search(r"(\d{3,})", text)
    if not match:
        return 1
    digits = match.group(1)
    return int(digits[:-2] or 1)


def _validate_row(row, raw_start, raw_end, raw_cycle, raw_rate):
    errors = []
    if not row["room_number"]:
        errors.append("房号为空")
    if not (str(row["building"]).startswith("B") or str(row["unit"]).startswith("B")):
        errors.append("非出租合同资料")
    if not row["tenant_name"]:
        errors.append("租户为空")
    if raw_start and not row["contract_start"]:
        errors.append("合同开始日期异常")
    if raw_end and not row["contract_end"]:
        errors.append("合同结束日期异常")
    if not row["contract_start"] or not row["contract_end"]:
        errors.append("合同期不完整")
    if row["area"] <= 0:
        errors.append("面积异常")
    if raw_rate not in (None, "") and row["custom_rate"] is None:
        errors.append("物业费单价异常")
    if raw_cycle and not row["payment_cycle"]:
        errors.append("缴费周期无法识别")
    return errors


def _skip(result, row, reason):
    result["skipped"] += 1
    if len(result["skip_examples"]) < 8:
        result["skip_examples"].append(f"第{row.get('row_no')}行: {reason}")
    result["problem_rows"].append({"row_no": row.get("row_no"), "reason": reason, "raw": " | ".join(str(row.get(k) or "") for k in ("building", "unit", "room_number", "tenant_name", "contract_start", "contract_end"))})


def _get(d, key, default=""):
    try:
        value = d.getvalue(key, default)
    except AttributeError:
        value = d.get(key, default)
        if isinstance(value, list):
            value = value[0] if value else default
    return default if value is None else str(value).strip()
