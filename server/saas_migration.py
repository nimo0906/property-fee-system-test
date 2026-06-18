#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite to SaaS PostgreSQL migration planning helpers."""

from server.db import get_db


def _table_exists(conn, table):
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def _count(conn, table):
    if not _table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)


def _money(value):
    return round(float(value or 0), 2)


def build_saas_migration_plan(tenant_name, project_name):
    conn = get_db()
    bill_total = conn.execute("SELECT COALESCE(SUM(amount),0) FROM bills").fetchone()[0] if _table_exists(conn, "bills") else 0
    pay_total = conn.execute("SELECT COALESCE(SUM(amount_paid),0) FROM payments").fetchone()[0] if _table_exists(conn, "payments") else 0
    service_period_count = conn.execute("""SELECT COUNT(*) FROM bills
        WHERE COALESCE(service_start,'')<>'' AND COALESCE(service_end,'')<>''""").fetchone()[0] if _table_exists(conn, "bills") else 0
    period_count = conn.execute("SELECT COUNT(DISTINCT billing_period) FROM bills").fetchone()[0] if _table_exists(conn, "bills") else 0
    counts = {
        "owners": _count(conn, "owners"),
        "charge_targets": _count(conn, "rooms"),
        "fee_types": _count(conn, "fee_types"),
        "bills": _count(conn, "bills"),
        "payments": _count(conn, "payments"),
        "contracts": _count(conn, "merchant_contracts"),
    }
    conn.close()
    bill_total = _money(bill_total)
    pay_total = _money(pay_total)
    checks = [
        {"name": "数量一致", "sqlite_value": counts, "postgres_expected": counts, "status": "待导入后核对"},
        {"name": "金额一致", "sqlite_value": bill_total, "postgres_expected": bill_total, "status": "待导入后核对"},
        {"name": "收款一致", "sqlite_value": pay_total, "postgres_expected": pay_total, "status": "待导入后核对"},
        {"name": "账期一致", "sqlite_value": int(period_count or 0), "postgres_expected": int(period_count or 0), "status": "待导入后核对"},
        {"name": "服务期一致", "sqlite_value": int(service_period_count or 0), "postgres_expected": int(service_period_count or 0), "status": "待导入后核对"},
    ]
    return {
        "tenant_name": tenant_name,
        "project_name": project_name,
        "counts": counts,
        "money": {
            "bill_amount_total": bill_total,
            "payment_amount_total": pay_total,
            "unpaid_amount_total": _money(bill_total - pay_total),
        },
        "checks": checks,
    }
