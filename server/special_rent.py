#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Special rent rules based on turnover sharing."""

from server.bill_snapshots import contract_snapshot, apply_snapshot
from server.contract_billing import get_contract_fee_type_id
from server.data_health import cleanup_invalid_payments
from server.db import get_db

SPECIAL_TYPES = {
    "fixed_plus_turnover": "固定租金+销售额分成",
    "higher_of_fixed_or_turnover": "保底租金与销售额分成取高",
    "turnover_only": "纯销售额分成",
}


def ensure_special_rent_tables(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS contract_special_rent_rules(
      id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL UNIQUE,
      rent_mode TEXT NOT NULL DEFAULT 'fixed',
      turnover_rate REAL NOT NULL DEFAULT 0, fixed_amount REAL NOT NULL DEFAULT 0,
      notes TEXT, created_at TEXT DEFAULT (datetime('now','localtime')));
    CREATE TABLE IF NOT EXISTS contract_turnover_records(
      id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL,
      billing_period TEXT NOT NULL, turnover_amount REAL NOT NULL DEFAULT 0,
      rent_amount REAL NOT NULL DEFAULT 0, operator TEXT, notes TEXT,
      bill_id INTEGER, created_at TEXT DEFAULT (datetime('now','localtime')),
      UNIQUE(contract_id,billing_period));
    CREATE INDEX IF NOT EXISTS idx_turnover_contract_period
      ON contract_turnover_records(contract_id,billing_period);
    """)


def detect_special_rent_mode(text):
    raw = str(text or "")
    if not any(k in raw for k in ("%", "％", "销售额", "营业额", "提成", "分成", "保底")):
        return "fixed"
    if "取其高" in raw or "取高" in raw or "保底" in raw:
        return "higher_of_fixed_or_turnover"
    if "固定" in raw or "月租" in raw:
        return "fixed_plus_turnover"
    return "turnover_only"


def extract_turnover_rate(text):
    raw = str(text or "").replace("％", "%")
    import re
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", raw)
    return float(match.group(1)) / 100 if match else 0.0


def upsert_special_rent_rule(db, contract_id, mode, rate, fixed_amount, notes=""):
    ensure_special_rent_tables(db)
    if not mode or mode == "fixed":
        db.execute("DELETE FROM contract_special_rent_rules WHERE contract_id=?", (contract_id,))
        return
    db.execute("""INSERT INTO contract_special_rent_rules(contract_id,rent_mode,turnover_rate,fixed_amount,notes)
        VALUES(?,?,?,?,?)
        ON CONFLICT(contract_id) DO UPDATE SET rent_mode=excluded.rent_mode,
        turnover_rate=excluded.turnover_rate,fixed_amount=excluded.fixed_amount,notes=excluded.notes""",
        (contract_id, mode, float(rate or 0), float(fixed_amount or 0), notes or ""))


def special_rule_for(db, contract_id):
    ensure_special_rent_tables(db)
    return db.execute("SELECT * FROM contract_special_rent_rules WHERE contract_id=?", (contract_id,)).fetchone()


def calc_special_rent(rule, turnover):
    fixed = float(rule["fixed_amount"] or 0)
    share = float(turnover or 0) * float(rule["turnover_rate"] or 0)
    if rule["rent_mode"] == "fixed_plus_turnover":
        return round(fixed + share, 2)
    if rule["rent_mode"] == "higher_of_fixed_or_turnover":
        return round(max(fixed, share), 2)
    return round(share, 2)


def create_turnover_rent_bill(contract_id, billing_period, turnover, operator="", notes=""):
    db = get_db()
    cleanup_invalid_payments(db)
    ensure_special_rent_tables(db)
    c = db.execute("SELECT * FROM merchant_contracts WHERE id=? AND status='active'", (contract_id,)).fetchone()
    rule = special_rule_for(db, contract_id)
    if not c or not rule:
        db.close(); raise ValueError("合同不存在或未设置特殊计租")
    amount = calc_special_rent(rule, turnover)
    exists = db.execute("SELECT id FROM contract_turnover_records WHERE contract_id=? AND billing_period=?",
                        (contract_id, billing_period)).fetchone()
    if exists:
        db.close(); raise ValueError("该账期销售额租金已生成")
    fee_id = get_contract_fee_type_id(db, "合同租金")
    service_start = f"{billing_period}-01"
    service_end = service_start
    bill_no = f"MCT-{contract_id}-{billing_period}"
    cur = db.execute("""INSERT INTO bills(room_id,commercial_space_id,owner_id,fee_type_id,billing_period,amount,due_date,status,bill_number,notes,source,source_ref,service_start,service_end)
        VALUES(?,?,?,?,?,?,?,'unpaid',?,?,?,?,?,?)""",
        (c["room_id"], c["commercial_space_id"], c["owner_id"], fee_id, billing_period, amount, service_end,
         bill_no, f"特殊计租销售额出账：销售额{turnover}，操作员：{operator}；{notes}",
         "merchant_contract", str(contract_id), service_start, service_end))
    apply_snapshot(db, cur.lastrowid, contract_snapshot(db, contract_id))
    db.execute("""INSERT INTO contract_turnover_records(contract_id,billing_period,turnover_amount,rent_amount,operator,notes,bill_id)
        VALUES(?,?,?,?,?,?,?)""", (contract_id, billing_period, float(turnover or 0), amount, operator, notes, cur.lastrowid))
    db.commit(); db.close()
    return {"bill_id": cur.lastrowid, "amount": amount}
