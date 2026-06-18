#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merchant contract lifecycle pages: detail, edit, renew, deactivate, bill view."""

import json
import urllib.parse

from server.backups import create_db_backup
from server.base import BaseHandler
from server.contract_billing import create_merchant_contract
from server.db import get_db, h, m, qs
from server.merchant_contract_attachments import render_contract_attachments
from server.merchant_contracts import CYCLE_LABELS, contract_status_label, _cycle_options, _deposit_total_from_form, _deposit_unit_price, _rent_mode_options, _rent_monthly_total_from_form, _rent_unit_price, _space_id_from_contract_form
from server.special_rent import SPECIAL_TYPES, ensure_special_rent_tables, special_rule_for


FIELD_LABELS = {
    "contract_no": "合同编号",
    "merchant_name": "商户/店名",
    "rent_amount": "租金单价",
    "rent_cycle": "租金周期",
    "property_rate": "物业费单价",
    "property_cycle": "物业费周期",
    "deposit_amount": "押金单价",
    "start_date": "开始日期",
    "end_date": "结束日期",
    "status": "合同状态",
    "notes": "备注",
}


ACTION_LABELS = {
    "merchant_contract_update": "编辑商户合同",
    "merchant_contract_renew": "合同续签",
    "merchant_contract_deactivate": "停用商户合同",
    "contract_amendment_recognize": "识别补充协议",
    "contract_amendment_confirm": "确认补充协议",
}


def _contract_row(contract_id):
    db = get_db()
    row = db.execute(
        """SELECT c.*,COALESCE(NULLIF(c.contract_area,0),s.area,r.area,0) area
           FROM merchant_contracts c
           LEFT JOIN rooms r ON c.room_id=r.id
           LEFT JOIN commercial_spaces s ON c.commercial_space_id=s.id
           WHERE c.id=?""",
        (contract_id,),
    ).fetchone()
    db.close()
    return row


def _bill_count(contract_id):
    db = get_db()
    count = db.execute(
        "SELECT COUNT(*) FROM bills WHERE source='merchant_contract' AND source_ref=?",
        (str(contract_id),),
    ).fetchone()[0]
    db.close()
    return int(count or 0)


def _contract_bills(contract_id):
    db = get_db()
    rows = db.execute(
        """SELECT b.*,f.name fee_name FROM bills b JOIN fee_types f ON b.fee_type_id=f.id
           WHERE b.source='merchant_contract' AND b.source_ref=?
           ORDER BY b.service_start,b.id""",
        (str(contract_id),),
    ).fetchall()
    db.close()
    return rows


def _contract_amendment_rows(contract_id):
    db = get_db()
    rows = db.execute(
        """SELECT * FROM contract_amendments
           WHERE contract_id=? ORDER BY effective_date DESC,id DESC""",
        (contract_id,),
    ).fetchall()
    db.close()
    return rows


def _safe_return_url(raw, fallback="/merchant_contracts"):
    parsed = urllib.parse.urlparse(raw or "")
    path = parsed.path if parsed.scheme or parsed.netloc else (raw or "")
    query = parsed.query
    if not path.startswith("/merchant_contracts"):
        return fallback
    if path.endswith("/edit"):
        return fallback
    return path + (f"?{query}" if query else "")


def render_contract_amendments(contract_id):
    rows = _contract_amendment_rows(contract_id)
    body = ''.join(
        f"""<tr><td>{h(r['effective_date'])}</td><td class="text-end">{m(r['rent_unit_price'])}</td>
        <td class="text-end">{m(r['rent_amount'])}</td><td class="text-end">{m(r['property_rate'])}</td>
        <td>{h(r['notes'] or '-')}</td></tr>"""
        for r in rows
    ) or '<tr><td colspan="5" class="text-center text-muted py-3">暂无已确认补充协议</td></tr>'
    return f"""<div class="card mb-3"><div class="card-header">已确认补充协议</div>
    <div class="table-responsive"><table class="table table-sm mb-0">
    <thead><tr><th>生效日期</th><th class="text-end">租金单价</th><th class="text-end">月租金总额</th>
    <th class="text-end">物业费单价</th><th>备注</th></tr></thead><tbody>{body}</tbody></table></div></div>"""


def render_special_rent_rule(contract_id):
    db = get_db()
    ensure_special_rent_tables(db)
    rule = special_rule_for(db, contract_id)
    db.close()
    if not rule:
        return ""
    return f"""<div class="card mb-3 border-warning"><div class="card-header text-warning">
    <i class="bi bi-percent"></i> 特殊计租</div><div class="card-body row g-2">
    <div class="col-md-3"><span class="text-muted small">计租方式</span><div>{h(SPECIAL_TYPES.get(rule['rent_mode'], rule['rent_mode']))}</div></div>
    <div class="col-md-3"><span class="text-muted small">保底/月固定租金</span><div>¥{m(rule['fixed_amount'])}</div></div>
    <div class="col-md-3"><span class="text-muted small">销售额分成比例</span><div>{m(float(rule['turnover_rate'] or 0) * 100)}%</div></div>
    <div class="col-md-3 text-end"><a class="btn btn-warning btn-sm" href="/merchant_contracts/{contract_id}/turnover_rent">销售额出账</a></div>
    <div class="col-12 small text-muted">该合同租金需每期录入销售额后人工确认出账，系统不会自动按普通固定租金生成。</div>
    </div></div>"""


def _audit_data(raw):
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


def _audit_diff(old_raw, new_raw):
    old = _audit_data(old_raw)
    new = _audit_data(new_raw)
    rows = []
    for key, label in FIELD_LABELS.items():
        if key in old or key in new:
            before = old.get(key, "")
            after = new.get(key, "")
            if str(before) != str(after):
                rows.append(f"<tr><td>{h(label)}</td><td>{h(before)}</td><td>{h(after)}</td></tr>")
    if "new_contract_id" in new:
        rows.append(f"<tr><td>新合同</td><td>-</td><td>#{h(new['new_contract_id'])}</td></tr>")
    if "backup" in new:
        rows.append(f"<tr><td>自动备份</td><td>-</td><td>{h(new['backup'])}</td></tr>")
    if not rows:
        return '<span class="text-muted">无字段差异</span>'
    return '<table class="table table-sm table-bordered mb-0"><thead><tr><th>字段</th><th>原值</th><th>新值</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def _contract_target_options(contract):
    db = get_db()
    spaces = db.execute("SELECT * FROM commercial_spaces WHERE status='active' ORDER BY space_no,id").fetchall()
    if spaces:
        db.close()
        selected_id = contract['commercial_space_id'] if 'commercial_space_id' in contract.keys() else None
        opts = "".join(
            f"""<option value="{r['id']}" {"selected" if int(r['id']) == int(selected_id or 0) else ""}>
            {h(r['space_no'])} / {h(r['shop_name'] or r['merchant_name'] or '-')} / {m(r['area'])}m²</option>"""
            for r in spaces
        )
        return 'commercial_space_id', opts, '空间来自“空间合同档案”。'
    rooms = db.execute(
        """SELECT r.id,r.building,r.unit,r.room_number,r.area,r.shop_name,r.owner_id,o.name owner_name
           FROM rooms r LEFT JOIN owners o ON r.owner_id=o.id
           WHERE r.category IN('商户','商业')
           ORDER BY r.room_number"""
    ).fetchall()
    db.close()
    selected_id = contract['room_id'] if 'room_id' in contract.keys() else None
    opts = "".join(
        f"""<option value="{r['id']}" {"selected" if int(r['id']) == int(selected_id or 0) else ""}>
        {h(r['building'])}-{h(r['room_number'])} / {h(r['shop_name'] or r['owner_name'] or '-')} / {m(r['area'])}m²</option>"""
        for r in rooms
    )
    return 'room_id', opts, '当前还没有空间档案，临时兼容旧商业收费对象；建议先到空间合同档案新增空间。'


def _contract_form_html(contract, action, title, warning="", return_url="/merchant_contracts"):
    db = get_db()
    space = None
    room = None
    if contract["commercial_space_id"]:
        space = db.execute("SELECT * FROM commercial_spaces WHERE id=?", (contract["commercial_space_id"],)).fetchone()
    elif contract["room_id"]:
        room = db.execute("SELECT * FROM rooms WHERE id=?", (contract["room_id"],)).fetchone()
    ensure_special_rent_tables(db)
    special_rule = special_rule_for(db, contract["id"])
    db.close()
    def space_val(key, fallback=""):
        if space and key in space.keys() and space[key] is not None:
            return h(space[key])
        if room:
            mapping = {"space_no": "room_number", "area": "area", "shop_name": "shop_name", "floor": "floor", "merchant_name": "shop_name"}
            source = mapping.get(key)
            if source and source in room.keys() and room[source] is not None:
                return h(room[source])
        return h(fallback)
    wt = space_val("water_rate_type", "非居民")
    status_options = "".join(
        f'<option value="{code}" {"selected" if contract["status"] == code else ""}>{label}</option>'
        for code, label in (("active", "启用"), ("inactive", "停用"), ("expired", "到期"))
    )
    hidden_target = ""
    target_summary = '<div class="alert alert-info">合同对象：商业空间合同。账单将绑定商业空间并进入商业账单体系。</div>'
    if contract["commercial_space_id"]:
        hidden_target = f'<input type="hidden" name="commercial_space_id" value="{h(contract["commercial_space_id"])}">'
    elif contract["room_id"]:
        hidden_target = f'<input type="hidden" name="room_id" value="{h(contract["room_id"])}">'
        target_summary = '<div class="alert alert-info">合同对象：收费对象合同。账单将绑定收费对象并进入账单、收据、催缴和报表体系。</div>'
    return f"""
    {warning}
    <form method="POST" action="{h(action)}" class="card">
      <div class="card-header d-flex justify-content-between align-items-center gap-2">
        <span><i class="bi bi-pencil-square"></i> {h(title)}</span>
        <a href="{h(return_url)}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-arrow-left"></i> 返回</a>
      </div>
      <div class="card-body row g-3">
        {hidden_target}
        <div class="col-12">{target_summary}</div>
        <div class="col-12"><h3 class="h6 text-muted border-bottom pb-2">空间资料</h3></div>
        <div class="col-md-3"><label>商户编号 *</label><input name="space_no" class="form-control" value="{space_val('space_no')}" required></div>
        <div class="col-md-3"><label>店铺名称</label><input name="shop_name" class="form-control" value="{space_val('shop_name', contract['shop_name'] or contract['merchant_name'])}"></div>
        <div class="col-md-3"><label>使用方/商户 *</label><input name="merchant_name" class="form-control" value="{h(contract['merchant_name'])}" required></div>
        <div class="col-md-3"><label>业态</label><input name="business_type" class="form-control" value="{space_val('business_type')}"></div>
        <div class="col-md-3"><label>楼层</label><input name="floor" type="number" class="form-control" value="{space_val('floor', 1)}"></div>
        <div class="col-md-3"><label>合同面积(m²) *</label><input name="area" type="number" step="0.01" class="form-control" value="{h(contract['contract_area'] or space_val('area', 0))}" required></div>
        <div class="col-md-3"><label>建筑面积(m²)</label><input name="building_area" type="number" step="0.01" class="form-control" value="{h(contract['building_area'] or space_val('area', 0))}"></div>
        <div class="col-md-3"><label>水费标准</label><select name="water_rate_type" class="form-select"><option value="非居民" {'selected' if wt=='非居民' else ''}>非居民</option><option value="特行" {'selected' if wt=='特行' else ''}>特行</option></select></div>
        <div class="col-md-3"><label>空间备注</label><input name="space_notes" class="form-control" value="{space_val('notes')}"></div>

        <div class="col-12 mt-2"><h3 class="h6 text-muted border-bottom pb-2">合同资料</h3></div>
        <div class="col-md-4"><label>合同编号</label><input name="contract_no" class="form-control" value="{h(contract['contract_no'])}" required></div>
        <input type="hidden" name="owner_id" value="{h(contract['owner_id'] or '')}">
        <div class="col-md-4"><label>租金单价（元/m²·月）</label><input name="rent_amount" type="number" step="0.01" class="form-control" value="{h(round(_rent_unit_price(contract['rent_amount'], space_val('area', 0)), 4))}" required></div>
        <div class="col-md-4"><label>租金周期</label><select name="rent_cycle" class="form-select" required>{_cycle_options(contract['rent_cycle'])}</select></div>
        <div class="col-md-4"><label>特殊计租方式</label><select name="rent_mode" class="form-select">{_rent_mode_options(special_rule['rent_mode'] if special_rule else 'fixed')}</select></div>
        <div class="col-md-4"><label>销售额分成比例</label><input name="turnover_rate" type="number" step="0.0001" min="0" class="form-control" value="{h(special_rule['turnover_rate'] if special_rule else '')}" placeholder="如 0.1 表示10%"></div>
        <div class="col-md-4"><label>物业费单价（元/m²·月）</label><input name="property_rate" type="number" step="0.0001" class="form-control" value="{h(contract['property_rate'])}" required></div>
        <div class="col-md-4"><label>物业费周期</label><select name="property_cycle" class="form-select" required>{_cycle_options(contract['property_cycle'])}</select></div>
        <div class="col-md-4"><label>押金单价（元/m²）</label><input name="deposit_amount" type="number" step="0.01" class="form-control" value="{h(round(_deposit_unit_price(contract['deposit_amount'], space_val('area', 0)), 4))}" required></div>
        <div class="col-md-4"><label>合同状态</label><select name="status" class="form-select">{status_options}</select></div>
        <div class="col-md-4"><label>开始日期</label><input name="start_date" type="date" class="form-control" value="{h(contract['start_date'])}" required></div>
        <div class="col-md-4"><label>结束日期</label><input name="end_date" type="date" class="form-control" value="{h(contract['end_date'])}" required></div>
        <div class="col-md-4"><label>合同备注</label><input name="notes" class="form-control" value="{h(contract['notes'] or '')}"></div>
        <div class="col-12"><button class="btn btn-primary">保存合同</button> <a href="{h(return_url)}" class="btn btn-outline-secondary">取消</a></div>
      </div>
    </form>"""

__all__ = [name for name in globals() if not name.startswith('__')]
