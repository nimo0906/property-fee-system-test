#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize form rows and persist commercial contract import rows."""

from server.db import h
from server.import_views import _form_value
from server.merchant_contract_import_parser import _clean, _end_date, _num, _row_errors
from server.special_rent import (
    detect_special_rent_mode,
    extract_turnover_rate,
    upsert_special_rent_rule,
)


def _notes(row):
    parts = []
    for label, key in [("进场日", "entry_date"), ("免租装修期", "free_period"), ("经营管理费/㎡", "management_rate"), ("垃圾费/㎡", "garbage_rate"), ("水费/吨", "water_rate"), ("电费/度", "electricity_rate"), ("递增", "increase_rule"), ("原备注", "notes")]:
        value = row.get(key)
        if value not in (None, "", 0, 0.0):
            parts.append(f"{label}：{value}")
    return "；".join(parts)


def _safe_int(value, default=0):
    try:
        return int(float(_clean(value)))
    except (TypeError, ValueError):
        return default


def _turnover_rate(value, fallback_text=""):
    rate = _num(value)
    if not rate:
        rate = extract_turnover_rate(fallback_text)
    if rate > 1:
        rate = rate / 100
    return rate


def _storage_contract_no(db, base_no, space_id, space_no):
    existing = db.execute(
        "SELECT commercial_space_id FROM merchant_contracts WHERE contract_no=?",
        (base_no,),
    ).fetchone()
    if not existing or existing["commercial_space_id"] == space_id:
        return base_no
    candidate = f"{base_no}-{space_no}"
    n = 2
    while db.execute("SELECT id FROM merchant_contracts WHERE contract_no=? AND commercial_space_id<>?", (candidate, space_id)).fetchone():
        candidate = f"{base_no}-{space_no}-{n}"
        n += 1
    return candidate


def _rows_from_form(d):
    try:
        count = int(_form_value(d, "row_count", "0") or 0)
    except ValueError:
        count = 0
    rows = []
    for i in range(count):
        if _form_value(d, f"include_{i}") != "1":
            continue
        space_no = _form_value(d, f"space_no_{i}").strip()
        contract_no = _form_value(d, f"contract_no_{i}").strip()
        merchant = _form_value(d, f"merchant_name_{i}").strip()
        start = _form_value(d, f"start_date_{i}").strip()
        lease_term = _form_value(d, f"lease_term_{i}").strip()
        contract_area = _num(_form_value(d, f"contract_area_{i}"))
        rent_rate = _num(_form_value(d, f"rent_rate_{i}"))
        notes = _form_value(d, f"notes_{i}").strip()
        rent_raw = _form_value(d, f"rent_raw_{i}").strip()
        special_text = " ".join(x for x in (rent_raw, notes) if x)
        rent_mode = _form_value(d, f"rent_mode_{i}").strip()
        if not rent_mode:
            rent_mode = detect_special_rent_mode(special_text)
        turnover_rate = _turnover_rate(_form_value(d, f"turnover_rate_{i}"), special_text)
        row = {
            "row_no": _safe_int(_form_value(d, f"row_no_{i}"), i + 1),
            "floor": _safe_int(_form_value(d, f"floor_{i}"), 1),
            "contract_no": contract_no or f"HT-{space_no}",
            "space_no": space_no,
            "start_date": start,
            "end_date": _form_value(d, f"end_date_{i}").strip() or _end_date(start, lease_term),
            "merchant_name": merchant,
            "entry_date": _form_value(d, f"entry_date_{i}").strip(),
            "free_period": _form_value(d, f"free_period_{i}").strip(),
            "contract_area": contract_area,
            "building_area": _num(_form_value(d, f"building_area_{i}")),
            "lease_term": lease_term,
            "shop_name": _form_value(d, f"shop_name_{i}").strip() or merchant,
            "phone": _form_value(d, f"phone_{i}").strip(),
            "rent_cycle": _form_value(d, f"rent_cycle_{i}").strip() or "monthly",
            "deposit_amount": _num(_form_value(d, f"deposit_amount_{i}")),
            "management_rate": _num(_form_value(d, f"management_rate_{i}")),
            "rent_rate": rent_rate,
            "rent_raw": rent_raw,
            "rent_mode": rent_mode or "fixed",
            "turnover_rate": turnover_rate,
            "property_rate": _num(_form_value(d, f"property_rate_{i}")),
            "garbage_rate": _num(_form_value(d, f"garbage_rate_{i}")),
            "water_rate": _num(_form_value(d, f"water_rate_{i}")),
            "electricity_rate": _num(_form_value(d, f"electricity_rate_{i}")),
            "increase_rule": _form_value(d, f"increase_rule_{i}").strip(),
            "notes": notes,
        }
        row["errors"] = _row_errors(space_no, contract_no, merchant, start, lease_term, contract_area, rent_rate, special_text)
        if row["rent_mode"] != "fixed":
            row["errors"] = [e for e in row["errors"] if "租金单价" not in e and "百分比/销售额" not in e]
        rows.append(row)
    return rows


def _upsert_row(db, row):
    existing_space = db.execute("SELECT id FROM commercial_spaces WHERE space_no=?", (row["space_no"],)).fetchone()
    if existing_space:
        space_id = existing_space["id"]
        db.execute(
            """UPDATE commercial_spaces SET floor=?,area=?,shop_name=?,merchant_name=?,water_rate_type='非居民',status='active',notes=? WHERE id=?""",
            (row["floor"], row["contract_area"], row["shop_name"], row["merchant_name"], _notes(row), space_id),
        )
    else:
        cur = db.execute(
            """INSERT INTO commercial_spaces(project_id,space_no,floor,area,shop_name,merchant_name,water_rate_type,status,notes)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (1, row["space_no"], row["floor"], row["contract_area"], row["shop_name"], row["merchant_name"], "非居民", "active", _notes(row)),
        )
        space_id = cur.lastrowid
    rent_amount = row["contract_area"] * row["rent_rate"]
    contract_no = _storage_contract_no(db, row["contract_no"], space_id, row["space_no"])
    notes = _notes(row)
    if contract_no != row["contract_no"] and f"原合同编号：{row['contract_no']}" not in notes:
        notes = (notes + "；" if notes else "") + f"原合同编号：{row['contract_no']}"
    existing_contract = db.execute(
        "SELECT id FROM merchant_contracts WHERE contract_no=? AND commercial_space_id=?",
        (contract_no, space_id),
    ).fetchone()
    values = (
        space_id, contract_no, row["merchant_name"], row["shop_name"], rent_amount,
        row["rent_cycle"], row["property_rate"], row["rent_cycle"], row["deposit_amount"],
        row["start_date"], row["end_date"], "active", notes, row["contract_area"], row["building_area"],
    )
    if existing_contract:
        db.execute(
            """UPDATE merchant_contracts SET commercial_space_id=?,room_id=NULL,contract_no=?,merchant_name=?,shop_name=?,
               rent_amount=?,rent_cycle=?,property_rate=?,property_cycle=?,deposit_amount=?,start_date=?,end_date=?,status=?,notes=?,
               contract_area=?,building_area=? WHERE id=?""",
            values + (existing_contract["id"],),
        )
        contract_id = existing_contract["id"]
        result = "updated"
    else:
        cur = db.execute(
        """INSERT INTO merchant_contracts(project_id,commercial_space_id,contract_no,merchant_name,shop_name,
           rent_amount,rent_cycle,property_rate,property_cycle,deposit_amount,start_date,end_date,status,notes,contract_area,building_area)
           VALUES(1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        values,
        )
        contract_id = cur.lastrowid
        result = "created"
    if row.get("rent_mode") and row.get("rent_mode") != "fixed":
        upsert_special_rent_rule(db, contract_id, row["rent_mode"], row.get("turnover_rate"),
                                 rent_amount, notes)
    return result
