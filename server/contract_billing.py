#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merchant contract billing for mall commercial tenants."""

from datetime import datetime, timedelta

from server.bill_snapshots import contract_snapshot, apply_snapshot
from server.data_health import cleanup_invalid_payments
from server.db import get_db, add_months
from server.money import money_float


CONTRACT_FEE_TYPES = (
    ("合同租金", "fixed", "元/月", "合同约定商户租金"),
    ("合同物业费", "area", "元/m²·月", "合同约定商户物业费"),
    ("合同押金", "fixed", "元", "合同保证金/押金"),
)


def ensure_contract_fee_types(conn):
    for order, (name, calc_method, unit, notes) in enumerate(CONTRACT_FEE_TYPES, start=11):
        exists = conn.execute("SELECT id FROM fee_types WHERE name=?", (name,)).fetchone()
        if not exists:
            conn.execute(
                """INSERT INTO fee_types(name,calc_method,unit_price,unit,billing_cycle,sort_order,is_active,notes)
                   VALUES(?,?,0,?,'monthly',?,1,?)""",
                (name, calc_method, unit, order, notes),
            )


def get_contract_fee_type_id(conn, name):
    ensure_contract_fee_types(conn)
    row = conn.execute("SELECT id FROM fee_types WHERE name=?", (name,)).fetchone()
    return row["id"]


def create_merchant_contract(data):
    conn = get_db()
    ensure_contract_fee_types(conn)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO merchant_contracts(
            project_id,room_id,commercial_space_id,owner_id,contract_no,merchant_name,shop_name,
            rent_amount,rent_cycle,property_rate,property_cycle,deposit_amount,contract_area,building_area,
            start_date,end_date,status,notes
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            int(data.get("project_id") or 1),
            int(data["room_id"]) if data.get("room_id") else None,
            int(data.get("commercial_space_id") or data.get("space_id")) if (data.get("commercial_space_id") or data.get("space_id")) else None,
            data.get("owner_id"),
            data.get("contract_no") or f"HT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            data.get("merchant_name") or data.get("shop_name") or "",
            data.get("shop_name") or data.get("merchant_name") or "",
            float(data.get("rent_amount") or 0),
            data.get("rent_cycle") or "monthly",
            float(data.get("property_rate") or 0),
            data.get("property_cycle") or "monthly",
            float(data.get("deposit_amount") or 0),
            float(data.get("contract_area") or 0),
            float(data.get("building_area") or 0),
            data["start_date"],
            data["end_date"],
            data.get("status") or "active",
            data.get("notes") or "",
        ),
    )
    contract_id = cur.lastrowid
    conn.commit()
    conn.close()
    return contract_id


def _cycle_months(cycle):
    return {"monthly": 1, "quarterly": 3, "semiannual": 6, "yearly": 12}.get(str(cycle or "").strip(), 1)


def _parse_date(value):
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _period_label(start, end):
    if start.year == end.year and start.month == end.month:
        return f"{start.year}-{start.month:02d}"
    return f"{start.year}-{start.month:02d}~{end.year}-{end.month:02d}"


def _service_end(start, months, contract_end):
    end = add_months(start, months) - timedelta(days=1)
    return min(end, contract_end)


def _contract(conn, contract_id):
    return conn.execute(
        """SELECT c.*,
                  COALESCE(s.area,r.area,0) area,
                  COALESCE(s.space_no,r.room_number,'') object_no,
                  COALESCE(s.shop_name,c.shop_name,r.shop_name,'') object_name,
                  COALESCE(r.building,'商场') building,COALESCE(r.unit,'商场') unit,
                  r.room_number
           FROM merchant_contracts c
           LEFT JOIN rooms r ON c.room_id=r.id
           LEFT JOIN commercial_spaces s ON c.commercial_space_id=s.id
           WHERE c.id=? AND c.status='active'""",
        (contract_id,),
    ).fetchone()


def _existing_item(conn, contract_id, fee_type_id, start, end, deposit=False):
    if deposit:
        return conn.execute(
            """SELECT id FROM bills
               WHERE source='merchant_contract' AND source_ref=? AND fee_type_id=?""",
            (str(contract_id), fee_type_id),
        ).fetchone()
    return conn.execute(
        """SELECT id FROM bills
           WHERE source='merchant_contract' AND source_ref=? AND fee_type_id=?
             AND ((service_start=? AND service_end=?) OR (billing_period=? AND (service_start IS NULL OR service_start='')))""",
        (str(contract_id), fee_type_id, start, end, _period_label(_parse_date(start), _parse_date(end))),
    ).fetchone()


def _preview_item(conn, contract, fee_name, amount, start, end, months):
    fee_type_id = get_contract_fee_type_id(conn, fee_name)
    deposit = fee_name == "合同押金"
    exists = _existing_item(conn, contract["id"], fee_type_id, start.isoformat(), end.isoformat(), deposit)
    return {
        "contract_id": contract["id"],
        "room_id": contract["room_id"],
        "commercial_space_id": contract["commercial_space_id"],
        "owner_id": contract["owner_id"],
        "fee_type_id": fee_type_id,
        "fee_name": fee_name,
        "amount": money_float(amount),
        "billing_period": _period_label(start, end),
        "service_start": start.isoformat(),
        "service_end": end.isoformat(),
        "due_date": end.isoformat(),
        "months": months,
        "exists": bool(exists),
    }


def build_contract_billing_preview(contract_id, service_start):
    conn = get_db()
    ensure_contract_fee_types(conn)
    contract = _contract(conn, contract_id)
    if not contract:
        conn.close()
        raise ValueError("商户合同不存在或未启用")
    start = _parse_date(service_start or contract["start_date"])
    contract_start = _parse_date(contract["start_date"])
    contract_end = _parse_date(contract["end_date"])
    if start < contract_start:
        start = contract_start
    items = []
    if start <= contract_end:
        rent_months = _cycle_months(contract["rent_cycle"])
        rent_end = _service_end(start, rent_months, contract_end)
        from server.special_rent import special_rule_for
        if not special_rule_for(conn, contract["id"]):
            items.append(_preview_item(conn, contract, "合同租金", float(contract["rent_amount"] or 0) * rent_months, start, rent_end, rent_months))
        prop_months = _cycle_months(contract["property_cycle"])
        prop_end = _service_end(start, prop_months, contract_end)
        prop_amount = float(contract["area"] or 0) * float(contract["property_rate"] or 0) * prop_months
        items.append(_preview_item(conn, contract, "合同物业费", prop_amount, start, prop_end, prop_months))
    dep_start = contract_start
    dep_end = contract_end
    items.append(_preview_item(conn, contract, "合同押金", float(contract["deposit_amount"] or 0), dep_start, dep_end, 0))
    conn.close()
    return {"contract": dict(contract), "service_start": start.isoformat(), "items": items}


def confirm_contract_billing(contract_id, preview_items, operator="system"):
    conn = get_db()
    cleanup_invalid_payments(conn)
    ensure_contract_fee_types(conn)
    contract = _contract(conn, contract_id)
    if not contract:
        conn.close()
        raise ValueError("商户合同不存在或未启用")
    generated = 0
    total = 0.0
    generated_ids = []
    for item in preview_items:
        if item.get("amount", 0) <= 0:
            continue
        deposit = item["fee_name"] == "合同押金"
        if _existing_item(conn, contract_id, item["fee_type_id"], item["service_start"], item["service_end"], deposit):
            continue
        bill_number = f"MC-{contract_id}-{item['fee_type_id']}-{item['service_start']}-{item['service_end']}"
        cur = conn.execute(
            """INSERT INTO bills(room_id,commercial_space_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,notes,source,source_ref,service_start,service_end)
               VALUES(?,?,?,?,?,?,?,'unpaid',?,?,?,?,?,?)""",
            (
                contract["room_id"], contract["commercial_space_id"], contract["owner_id"], item["fee_type_id"], item["billing_period"],
                item["amount"], item["due_date"], bill_number,
                f"商户合同 {contract['contract_no']} 自动出账，操作员：{operator or 'system'}",
                "merchant_contract", str(contract_id), item["service_start"], item["service_end"],
            ),
        )
        apply_snapshot(conn, cur.lastrowid, contract_snapshot(conn, contract_id))
        generated += 1
        total += float(item["amount"])
        generated_ids.append(cur.lastrowid)
    if generated:
        label = preview_items[0]["billing_period"] if preview_items else ""
        conn.execute(
            """INSERT OR IGNORE INTO contract_bill_runs(project_id,contract_id,billing_period,generated_count,total_amount,operator)
               VALUES(?,?,?,?,?,?)""",
            (contract["project_id"], contract_id, label, generated, money_float(total), operator),
        )
    conn.commit()
    conn.close()
    return {"contract_id": contract_id, "generated_count": generated, "total_amount": money_float(total), "bill_ids": generated_ids}


def generate_contract_bills(contract_id, period, operator="system"):
    service_start = period if len(str(period or "")) >= 10 else f"{period}-01"
    preview = build_contract_billing_preview(contract_id, service_start)
    result = confirm_contract_billing(contract_id, preview["items"], operator)
    result["period"] = period
    return result
