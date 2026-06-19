#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 1 closure readiness check for SaaS cloud backoffice."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def require_file(path):
    full = ROOT / path
    require(full.exists(), f"missing file: {path}")
    return full


def require_text(path, items, forbidden=()):
    text = require_file(path).read_text(encoding="utf-8")
    for item in items:
        require(item in text, f"missing {path} item: {item}")
    for item in forbidden:
        require(item not in text, f"forbidden {path} item: {item}")
    return text


def main():
    report_items = [
        "第一阶段收口", "员工后台云端化", "登录、租户、角色权限", "收费对象", "收费项目",
        "账单生成", "账单审核", "收款登记", "收据", "导出", "对账报表", "数据导入",
        "审计日志", "备份恢复", "租户隔离", "客户上传数据与系统自身数据隔离",
        "业主端 H5 后置", "微信/支付宝真实支付后置", "授权云服务后台后置",
    ]
    require_text(
        "docs/saas-phase-1-closure-report.md",
        report_items,
        forbidden=("POSTGRES_PASSWORD=", "APP_SECRET_KEY=", "/Users/nimo"),
    )
    print("PASS saas phase1 closure report")

    for path in [
        "server/saas_acceptance_pages.py",
        "server/saas_deploy_pages.py",
        "server/saas_deploy.py",
        "server/saas_app.py",
        "server/saas_service.py",
        "server/saas_repository.py",
        "server/saas_import_pages.py",
        "server/saas_backup_pages.py",
        "server/saas_audit_log_pages.py",
        "scripts/saas_env_security_check.py",
        "scripts/saas_preflight_check.py",
        "scripts/saas_acceptance_check.py",
        "scripts/saas_ops_check.py",
        "scripts/saas_demo_tenant_drill.py",
        "scripts/saas_release_gate.py",
        "scripts/saas_isolation_evidence.py",
        "scripts/saas_release_evidence.py",
        "docs/saas-cloud-ops-runbook.md",
        "docs/saas-demo-tenant-drill.md",
    ]:
        require_file(path)
    print("PASS saas phase1 required assets")

    test_files = [
        "tests/test_saas_cross_tenant_isolation.py",
        "tests/test_saas_permission_matrix.py",
        "tests/test_saas_import_review_flow.py",
        "tests/test_saas_receipt_export_report.py",
        "tests/test_saas_ops_runbook_assets.py",
    ]
    for path in test_files:
        require_file(path)
    print("PASS saas phase1 required tests")

    deploy = require_file("server/saas_deploy.py").read_text(encoding="utf-8")
    require("scripts/saas_phase1_closure_check.py" in deploy, "closure script not in deploy assets")
    require("docs/saas-phase-1-closure-report.md" in deploy, "closure report not in deploy assets")
    print("PASS saas phase1 deploy registration")

    print("saas_phase1_closure_check: PASS")


if __name__ == "__main__":
    main()
