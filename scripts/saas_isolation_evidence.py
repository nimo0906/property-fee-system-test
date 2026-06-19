#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate tenant isolation evidence detail for SaaS release."""

from pathlib import Path
import datetime as dt
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_storage import SaasStorage

REPORT = ROOT / "release" / "saas-isolation-evidence.md"


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


def login(client, tenant, project, username):
    post_ok(client, "/api/auth/login", {
        "tenant_name": tenant,
        "project_name": project,
        "username": username,
        "role_code": "system_admin",
    })


def seed_tenant_a(client):
    target = post_ok(client, "/api/charge-targets", {
        "building": "A样例楼栋",
        "unit": "1单元",
        "room_number": "A-101",
        "category": "住宅",
        "area": 80,
    })["item"]
    fee = post_ok(client, "/api/fee-types", {"name": "A物业费", "unit_price": 3})["item"]
    bill = post_ok(client, "/api/bills/generate", {
        "target_id": target["id"],
        "fee_type_id": fee["id"],
        "billing_period": "2026-08",
        "service_start": "2026-08-01",
        "service_end": "2026-08-31",
    })["item"]
    approved = post_ok(client, f"/api/bills/{bill['id']}/approve")["item"]
    payment = post_ok(client, "/api/payments", {
        "bill_id": bill["id"],
        "amount": 120,
        "method": "evidence",
        "idempotency_key": "ISO-EVIDENCE-A-1",
    })["item"]
    backup = post_ok(client, "/api/backups/create")["item"]
    drill = post_ok(client, "/api/restore-drills", {"backup_id": backup["backup_id"], "scope": "database"})["item"]
    return {"target": target, "bill": approved, "payment": payment, "backup": backup, "drill": drill}


def collect_evidence():
    app = create_app()
    tenant_a = TestClient(app)
    tenant_b = TestClient(app)
    login(tenant_a, "A样例公司", "A样例项目", "admin_a")
    login(tenant_b, "B样例公司", "B样例项目", "admin_b")
    a = seed_tenant_a(tenant_a)

    b_targets = get_ok(tenant_b, "/api/charge-targets")["items"]
    b_bills = get_ok(tenant_b, "/api/bills/search?period=2026-08")["items"]
    b_payments = get_ok(tenant_b, "/api/payments?period=2026-08")["items"]
    b_report = get_ok(tenant_b, "/api/reports/summary?period=2026-08")
    b_audits = get_ok(tenant_b, "/api/audit-logs")["items"]
    b_backups = get_ok(tenant_b, "/api/backups")["items"]

    require(b_targets == [], "tenant B saw tenant A charge targets")
    require(b_bills == [], "tenant B saw tenant A bills")
    require(b_payments == [], "tenant B saw tenant A payments")
    require(b_report["bill_count"] == 0, "tenant B saw tenant A report totals")
    require("A样例楼栋" not in str(b_audits), "tenant B saw tenant A audit detail")
    require(b_backups == [], "tenant B saw tenant A backup records")

    storage = SaasStorage(root_dir="/var/lib/property-saas")
    tenant_file = storage.upload_path(tenant_id=1, project_id=2, upload_id=3, category="imports", filename="owners.xlsx")
    system_file = storage.system_asset_path("templates", "bill.xlsx")
    require(tenant_file.startswith("tenants/"), "tenant file not in tenant prefix")
    require(system_file.startswith("system/"), "system file not in system prefix")
    require(tenant_file.split("/")[0] != system_file.split("/")[0], "tenant and system prefixes overlap")

    return {
        "target_id": a["target"]["id"],
        "bill_id": a["bill"]["id"],
        "payment_id": a["payment"]["id"],
        "backup_id": a["backup"]["backup_id"],
        "drill_scope": a["drill"]["scope"],
        "tenant_file": tenant_file,
        "system_file": system_file,
    }


def build_report(evidence):
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    rows = [
        ("收费对象隔离", "B样例公司不能读取 A样例公司收费对象", "PASS"),
        ("账单隔离", "B样例公司不能读取 A样例公司账单", "PASS"),
        ("收款隔离", "B样例公司不能读取 A样例公司收款流水", "PASS"),
        ("报表隔离", "B样例公司账期报表为 0", "PASS"),
        ("审计日志隔离", "B样例公司不能读取 A样例公司审计详情", "PASS"),
        ("备份恢复隔离", "B样例公司不能读取 A样例公司备份记录", "PASS"),
        ("客户上传数据与系统自身数据隔离", "tenant-files 与 system-files 前缀不同", "PASS"),
    ]
    table = "\n".join(f"| {name} | {detail} | {status} |" for name, detail, status in rows)
    return f"""# SaaS 租户隔离证据明细

生成时间：{now}

样例租户：A样例公司 / B样例公司。

| 检查项 | 证据 | 结果 |
| --- | --- | --- |
{table}

## 样例业务数据

- A样例公司收费对象 ID：{evidence['target_id']}
- A样例公司账单 ID：{evidence['bill_id']}
- A样例公司收款 ID：{evidence['payment_id']}
- A样例公司备份 ID：{evidence['backup_id']}
- 恢复演练范围：{evidence['drill_scope']}

## 文件隔离

- tenant-files：`{evidence['tenant_file']}`
- system-files：`{evidence['system_file']}`

结论：租户隔离、收费对象隔离、账单隔离、收款隔离、报表隔离、审计日志隔离、备份恢复隔离、客户上传数据与系统自身数据隔离均通过。
"""


def main():
    evidence = collect_evidence()
    text = build_report(evidence)
    for item in ["POSTGRES_PASSWORD=", "APP_SECRET_KEY=", "/Users/nimo", "真实客户"]:
        require(item not in text, f"forbidden evidence content: {item}")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(f"wrote {REPORT.relative_to(ROOT)}")
    print("saas_isolation_evidence: PASS")


if __name__ == "__main__":
    main()
