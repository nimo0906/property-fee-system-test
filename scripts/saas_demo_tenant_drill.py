#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a safe demo tenant acceptance drill for SaaS backoffice."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def post_ok(client, path, payload=None):
    response = client.post(path, json=payload or {})
    require(response.status_code == 200, f"{path} failed: {response.text}")
    return response.json()


def get_ok(client, path):
    response = client.get(path)
    require(response.status_code == 200, f"{path} failed: {response.text}")
    return response.json()


def seed_demo_tenant(client):
    login = post_ok(client, "/api/auth/login", {
        "tenant_name": "样例物业公司",
        "project_name": "样例云端项目",
        "username": "demo_admin",
        "role_code": "system_admin",
    })
    require(login.get("ok") is True, "demo tenant login failed")
    print("PASS demo tenant login")

    preview = post_ok(client, "/api/imports/charge-targets/preview", {"rows": [
        {"building": "一期住宅", "unit": "1单元", "room_number": "101", "category": "住宅", "area": "86.5"},
        {"building": "一期住宅", "unit": "1单元", "room_number": "102", "category": "住宅", "area": "92"},
        {"building": "商业街", "unit": "A区", "room_number": "A-01", "category": "商户", "area": "120"},
    ]})
    require(preview["valid_count"] == 3, "demo target preview mismatch")
    confirm = post_ok(client, "/api/imports/charge-targets/confirm", {"import_id": preview["import_id"]})
    require(confirm["created_count"] == 3, "demo target confirm mismatch")
    targets = get_ok(client, "/api/charge-targets")["items"]
    require(len(targets) == 3, "demo target count mismatch")
    print("PASS demo charge targets")

    property_fee = post_ok(client, "/api/fee-types", {"name": "物业费", "unit_price": 2.5})["item"]
    shop_fee = post_ok(client, "/api/fee-types", {"name": "商业物业费", "unit_price": 6})["item"]
    print("PASS demo fee types")
    return targets, property_fee, shop_fee


def run_billing(client, targets, property_fee, shop_fee):
    bills = []
    for target in targets:
        fee = shop_fee if target["category"] == "商户" else property_fee
        bill = post_ok(client, "/api/bills/generate", {
            "target_id": target["id"],
            "fee_type_id": fee["id"],
            "billing_period": "2026-07",
            "service_start": "2026-07-01",
            "service_end": "2026-07-31",
        })["item"]
        require(bill["status"] == "pending_review", "demo bill should need approval")
        bills.append(bill)
    require(len(bills) == 3, "demo bill count mismatch")
    print("PASS demo bill generation")

    for bill in bills:
        approved = post_ok(client, f"/api/bills/{bill['id']}/approve")["item"]
        require(approved["status"] == "unpaid", "demo bill approval mismatch")
    print("PASS demo bill approval")

    payments = [
        (bills[0], 216.25),
        (bills[1], 100.00),
        (bills[2], 720.00),
    ]
    for index, (bill, amount) in enumerate(payments, start=1):
        payment = post_ok(client, "/api/payments", {
            "bill_id": bill["id"],
            "amount": amount,
            "method": "demo",
            "idempotency_key": f"DEMO-202607-{index}",
        })["item"]
        require(payment["receipt_number"].startswith("RCPT-"), "demo receipt missing")
    print("PASS demo payments")


def verify_outputs(client):
    report = get_ok(client, "/api/reports/summary?period=2026-07")
    require(report["bill_count"] == 3, "demo report bill count mismatch")
    require(report["bill_amount_total"] == 1166.25, "demo report due mismatch")
    require(report["payment_amount_total"] == 1036.25, "demo report paid mismatch")
    require(report["unpaid_amount_total"] == 130.0, "demo report unpaid mismatch")
    print("PASS demo report totals")

    bills_export = get_ok(client, "/api/exports/bills?period=2026-07")
    payments_export = get_ok(client, "/api/exports/payments?period=2026-07")
    require("2026-07" in bills_export["content"], "demo bill export missing period")
    require("RCPT-" in payments_export["content"], "demo payment export missing receipt")
    print("PASS demo exports")

    backup = post_ok(client, "/api/backups/create")["item"]
    drill = post_ok(client, "/api/restore-drills", {"backup_id": backup["backup_id"], "scope": "database"})["item"]
    require(drill["scope"] == "database", "demo restore drill mismatch")
    print("PASS demo backup restore drill")


def verify_isolation():
    app = create_app()
    tenant_a = TestClient(app)
    targets, property_fee, shop_fee = seed_demo_tenant(tenant_a)
    run_billing(tenant_a, targets, property_fee, shop_fee)
    verify_outputs(tenant_a)

    tenant_b = TestClient(app)
    post_ok(tenant_b, "/api/auth/login", {
        "tenant_name": "样例物业公司B",
        "project_name": "样例云端项目B",
        "username": "demo_admin_b",
        "role_code": "system_admin",
    })
    require(get_ok(tenant_b, "/api/charge-targets")["items"] == [], "tenant B saw tenant A targets")
    require(get_ok(tenant_b, "/api/bills/search?period=2026-07")["total"] == 0, "tenant B saw tenant A bills")
    require(get_ok(tenant_b, "/api/reports/summary?period=2026-07")["bill_count"] == 0, "tenant B saw tenant A report")
    print("PASS demo tenant isolation")


def main():
    verify_isolation()
    print("saas_demo_tenant_drill: PASS")


if __name__ == "__main__":
    main()
