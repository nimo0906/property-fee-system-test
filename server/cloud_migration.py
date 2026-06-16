#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite to PostgreSQL seed export helpers for v2 cloud migration."""

import json
from datetime import datetime

from server.db import get_db

CORE_EXPORT_TABLES = (
    "projects",
    "owners",
    "rooms",
    "fee_types",
    "bills",
    "payments",
    "merchant_contracts",
    "contract_attachments",
    "contract_bill_runs",
)


def _table_exists(conn, table):
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def _count(conn, table):
    if not _table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)


def _money(value):
    return round(float(value or 0), 2)


def _check(name, value, description):
    return {
        "name": name,
        "sqlite_value": value,
        "postgres_expected": value,
        "status": "待导入后核对",
        "description": description,
    }


def build_migration_summary():
    conn = get_db()
    tables = {table: _count(conn, table) for table in CORE_EXPORT_TABLES}
    bill_total = conn.execute("SELECT COALESCE(SUM(amount),0) FROM bills").fetchone()[0] if _table_exists(conn, "bills") else 0
    pay_total = conn.execute("SELECT COALESCE(SUM(amount_paid),0) FROM payments").fetchone()[0] if _table_exists(conn, "payments") else 0
    b_tower_bill_total = conn.execute(
        """SELECT COALESCE(SUM(b.amount),0)
           FROM bills b JOIN rooms r ON b.room_id=r.id
           WHERE r.building='B座'"""
    ).fetchone()[0] if _table_exists(conn, "bills") and _table_exists(conn, "rooms") else 0
    mall_bill_total = conn.execute(
        """SELECT COALESCE(SUM(b.amount),0)
           FROM bills b JOIN rooms r ON b.room_id=r.id
           WHERE r.building='商场' OR r.unit='商场'"""
    ).fetchone()[0] if _table_exists(conn, "bills") and _table_exists(conn, "rooms") else 0
    service_period_bill_count = conn.execute(
        """SELECT COUNT(*) FROM bills
           WHERE COALESCE(service_start,'')<>'' AND COALESCE(service_end,'')<>''"""
    ).fetchone()[0] if _table_exists(conn, "bills") else 0
    mall_rooms = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE building='商场' OR unit='商场'"
    ).fetchone()[0] if _table_exists(conn, "rooms") else 0
    b_tower_rooms = conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE building='B座'"
    ).fetchone()[0] if _table_exists(conn, "rooms") else 0
    conn.close()
    bill_total = _money(bill_total)
    pay_total = _money(pay_total)
    unpaid_total = _money(bill_total - pay_total)
    validation_totals = {
        "owner_count": int(tables.get("owners", 0)),
        "room_count": int(tables.get("rooms", 0)),
        "bill_count": int(tables.get("bills", 0)),
        "payment_count": int(tables.get("payments", 0)),
        "bill_amount_total": bill_total,
        "payment_amount_total": pay_total,
        "unpaid_amount_total": unpaid_total,
    }
    validation_checks = (
        _check("业主数量一致", validation_totals["owner_count"], "导入 PostgreSQL 后 cloud/owners 侧业主数量应与 SQLite 当前值一致。"),
        _check("房间数量一致", validation_totals["room_count"], "导入 PostgreSQL 后房间/铺位数量应与 SQLite 当前值一致。"),
        _check("账单数量一致", validation_totals["bill_count"], "导入 PostgreSQL 后账单数量应与 SQLite 当前值一致。"),
        _check("收款数量一致", validation_totals["payment_count"], "导入 PostgreSQL 后收款记录数量应与 SQLite 当前值一致。"),
        _check("账单金额一致", validation_totals["bill_amount_total"], "导入 PostgreSQL 后账单金额合计应与 SQLite 当前值一致。"),
        _check("收款金额一致", validation_totals["payment_amount_total"], "导入 PostgreSQL 后收款金额合计应与 SQLite 当前值一致。"),
        _check("欠费金额一致", validation_totals["unpaid_amount_total"], "导入 PostgreSQL 后欠费金额应与账单金额减收款金额一致。"),
    )
    return {
        "target": "PostgreSQL commercial-complex cloud v2",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tables": tables,
        "money": {
            "bill_amount_total": bill_total,
            "payment_amount_total": pay_total,
            "unpaid_amount_total": unpaid_total,
        },
        "scope": {
            "b_tower_rooms": int(b_tower_rooms or 0),
            "mall_rooms": int(mall_rooms or 0),
        },
        "reconciliation": {
            "b_tower_bill_total": round(float(b_tower_bill_total or 0), 2),
            "mall_bill_total": round(float(mall_bill_total or 0), 2),
            "service_period_bill_count": int(service_period_bill_count or 0),
        },
        "validation_totals": validation_totals,
        "validation_checks": list(validation_checks),
    }


def _quote(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _table_columns(conn, table):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r["name"] for r in rows]


def _export_table(conn, table):
    if not _table_exists(conn, table):
        return f"-- {table}\n-- skipped: table does not exist\n"
    columns = _table_columns(conn, table)
    if not columns:
        return f"-- {table}\n-- skipped: no columns\n"
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall() if "id" in columns else conn.execute(f"SELECT * FROM {table}").fetchall()
    lines = [f"-- {table}"]
    if not rows:
        lines.append(f"-- no rows for {table}")
        return "\n".join(lines) + "\n"
    col_sql = ", ".join(columns)
    for row in rows:
        values = ", ".join(_quote(row[col]) for col in columns)
        lines.append(f"INSERT INTO {table} ({col_sql}) VALUES ({values}) ON CONFLICT DO NOTHING;")
    return "\n".join(lines) + "\n"


def export_postgres_seed_sql(tables=None):
    export_tables = tuple(tables or CORE_EXPORT_TABLES)
    conn = get_db()
    parts = [
        "-- PostgreSQL seed data exported from 物业管理收费系统 2.0 SQLite runtime",
        "-- Review before importing into production cloud database.",
        "BEGIN;",
    ]
    for table in export_tables:
        parts.append(_export_table(conn, table))
    summary = json.dumps(build_migration_summary(), ensure_ascii=False, sort_keys=True)
    parts.append("-- migration_summary")
    parts.append(f"-- {summary}")
    parts.append("COMMIT;")
    conn.close()
    return "\n".join(parts) + "\n"
