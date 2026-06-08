#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merchant contract billing for mall commercial tenants."""

from datetime import datetime

from server.db import get_db


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
            project_id,room_id,owner_id,contract_no,merchant_name,shop_name,
            rent_amount,rent_cycle,property_rate,property_cycle,deposit_amount,
            start_date,end_date,status,notes
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            int(data.get("project_id") or 1),
            int(data["room_id"]),
            data.get("owner_id"),
            data.get("contract_no") or f"HT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            data.get("merchant_name") or data.get("shop_name") or "",
            data.get("shop_name") or data.get("merchant_name") or "",
            float(data.get("rent_amount") or 0),
            data.get("rent_cycle") or "monthly",
            float(data.get("property_rate") or 0),
            data.get("property_cycle") or "monthly",
            float(data.get("deposit_amount") or 0),
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


def _bill_exists(conn, contract_id, period, fee_type_id):
    return conn.execute(
        """SELECT id FROM bills
           WHERE source='merchant_contract' AND source_ref=? AND billing_period=? AND fee_type_id=?""",
        (str(contract_id), period, fee_type_id),
    ).fetchone()


def _insert_bill(conn, contract, fee_type_name, period, amount, operator):
    fee_type_id = get_contract_fee_type_id(conn, fee_type_name)
    if amount <= 0 or _bill_exists(conn, contract["id"], period, fee_type_id):
        return 0
    bill_number = f"MC-{contract['id']}-{period}-{fee_type_id}"
    conn.execute(
        """INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,notes,source,source_ref)
           VALUES(?,?,?,?,?,date(? || '-01','+1 month','-1 day'),'unpaid',?,?,?,?)""",
        (
            contract["room_id"],
            contract["owner_id"],
            fee_type_id,
            period,
            round(float(amount), 2),
            period,
            bill_number,
            f"商户合同 {contract['contract_no']} 自动出账，操作员：{operator or 'system'}",
            "merchant_contract",
            str(contract["id"]),
        ),
    )
    return 1


def generate_contract_bills(contract_id, period, operator="system"):
    conn = get_db()
    ensure_contract_fee_types(conn)
    contract = conn.execute(
        """SELECT c.*,r.area FROM merchant_contracts c
           JOIN rooms r ON c.room_id=r.id WHERE c.id=? AND c.status='active'""",
        (contract_id,),
    ).fetchone()
    if not contract:
        conn.close()
        raise ValueError("商户合同不存在或未启用")
    generated = 0
    total = 0.0
    amounts = [
        ("合同租金", float(contract["rent_amount"] or 0)),
        ("合同物业费", float(contract["area"] or 0) * float(contract["property_rate"] or 0)),
        ("合同押金", float(contract["deposit_amount"] or 0)),
    ]
    for fee_name, amount in amounts:
        if _insert_bill(conn, contract, fee_name, period, amount, operator):
            generated += 1
            total += amount
    conn.execute(
        """INSERT OR IGNORE INTO contract_bill_runs(project_id,contract_id,billing_period,generated_count,total_amount,operator)
           VALUES(?,?,?,?,?,?)""",
        (contract["project_id"], contract_id, period, generated, round(total, 2), operator),
    )
    conn.commit()
    conn.close()
    return {"contract_id": contract_id, "period": period, "generated_count": generated, "total_amount": round(total, 2)}
