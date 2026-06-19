#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate sanitized SaaS release evidence report."""

from pathlib import Path
import datetime as dt

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REPORT = ROOT / "release" / "saas-release-evidence.md"
GATE_CHECKS = [
    "scripts/saas_env_security_check.py",
    "scripts/saas_preflight_check.py",
    "scripts/saas_ops_check.py",
    "scripts/saas_acceptance_check.py",
    "scripts/saas_phase1_closure_check.py",
    "scripts/saas_legacy_gap_check.py",
    "scripts/saas_demo_tenant_drill.py",
    "scripts/saas_license_cloud_boundary_check.py",
    "scripts/saas_license_cloud_management_check.py",
    "scripts/saas_license_status_integration_check.py",
    "scripts/saas_license_enforcement_check.py",
    "scripts/saas_license_enforcement_audit_check.py",
    "scripts/saas_license_seat_limit_check.py",
    "scripts/saas_license_ops_page_check.py",
    "scripts/saas_license_tenant_binding_check.py",
    "scripts/saas_license_binding_page_check.py",
    "scripts/saas_license_binding_persistence_check.py",
    "scripts/saas_license_binding_backup_check.py",
    "scripts/saas_license_binding_runbook_check.py",
    "scripts/saas_production_deployment_rehearsal_check.py",
    "scripts/saas_production_precheck.py",
    "scripts/saas_first_tenant_wizard_check.py",
    "scripts/saas_first_tenant_delivery_loop_check.py",
    "scripts/saas_first_tenant_acceptance_record_check.py",
    "scripts/saas_first_tenant_acceptance_export_check.py",
    "scripts/saas_first_tenant_delivery_package_check.py",
    "scripts/saas_tenant_business_template_check.py",
    "scripts/saas_tenant_business_config_check.py",
    "scripts/saas_tenant_business_config_page_check.py",
    "scripts/saas_fee_type_template_init_check.py",
    "scripts/saas_first_tenant_fee_init_delivery_check.py",
    "scripts/saas_first_tenant_acceptance_fee_review_check.py",
    "scripts/saas_first_tenant_acceptance_risk_warning_check.py",
    "scripts/saas_first_tenant_acceptance_risk_overview_check.py",
    "scripts/saas_first_tenant_acceptance_persistence_check.py",
    "scripts/saas_first_tenant_acceptance_backup_evidence_check.py",
    "scripts/saas_first_tenant_acceptance_backup_page_check.py",
    "scripts/saas_production_database_env_check.py",
    "scripts/saas_postgres_repository_compat_check.py",
    "scripts/saas_postgres_insert_id_check.py",
    "scripts/saas_systemd_env_file_check.py",
    "scripts/saas_production_deployment_commands_check.py",
    "scripts/saas_production_env_file_check.py",
    "scripts/saas_production_runtime_check.py",
    "scripts/saas_production_first_tenant_smoke.py",
    "scripts/saas_production_acceptance_gate.py",
    "scripts/saas_production_acceptance_result.py",
    "scripts/saas_isolation_evidence.py",
]
POSTPONED = [
    "业主端 H5 后置",
    "微信/支付宝真实支付后置",
    "电子票据平台对接后置",
    "授权云服务后台后置",
]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def asset_status(path):
    return "PASS" if (ROOT / path).exists() else "MISSING"


def build_report():
    from server.saas_deploy import ISOLATION_CONTRACT, REQUIRED_DEPLOY_FILES, validate_deployment_assets

    result = validate_deployment_assets(ROOT)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    check_rows = "\n".join(f"| {item} | {asset_status(item)} |" for item in GATE_CHECKS)
    asset_rows = "\n".join(f"| {item} | {asset_status(item)} |" for item in REQUIRED_DEPLOY_FILES)
    isolation_rows = "\n".join(f"| {name} | `{value}` |" for name, value in ISOLATION_CONTRACT.items())
    postponed_rows = "\n".join(f"- {item}" for item in POSTPONED)
    deploy_status = "PASS" if result.get("ok") else "WARN"
    return f"""# SaaS 云端商业版上线证据报告

生成时间：{now}

## 商业上线总门禁

上线前统一执行：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/property_pycache python3 scripts/saas_release_gate.py
```

| 子检查 | 资产状态 |
| --- | --- |
{check_rows}

## 部署资产

部署资产总状态：{deploy_status}

| 文件 | 状态 |
| --- | --- |
{asset_rows}

## 数据隔离证据

| 边界 | 目录 |
| --- | --- |
{isolation_rows}

验收重点：租户隔离；客户上传数据与系统自身数据隔离；备份、日志和系统文件不与租户业务文件混放。租户隔离证据明细见 `release/saas-isolation-evidence.md`。

## 业务闭环证据

- 登录、租户、角色权限已由 `scripts/saas_acceptance_check.py` 覆盖。
- 收费对象、收费项目、账单生成、账单审核、收款登记、对账报表、导出已由 `scripts/saas_acceptance_check.py` 和 `scripts/saas_demo_tenant_drill.py` 覆盖。
- 备份恢复演练、管理员密码重置流程、日志轮转由 `scripts/saas_ops_check.py` 覆盖。
- 第一阶段范围和后置边界由 `scripts/saas_phase1_closure_check.py` 覆盖。
- 原桌面业务迁移差距由 `scripts/saas_legacy_gap_check.py` 和 `docs/saas-legacy-business-migration-gap.md` 覆盖。
- 租户隔离证据明细由 `scripts/saas_isolation_evidence.py` 生成。

## 后置范围

{postponed_rows}

## 生产环境变量安全检查

- `scripts/saas_env_security_check.py` 只读取运行时环境变量。
- 报告和日志只允许显示变量名与长度，不允许显示密钥原文。

## 安全说明

本报告不包含生产密钥、数据库密码、真实环境变量、客户资料或本机绝对路径。
"""


def main():
    text = build_report()
    forbidden = ["POSTGRES_PASSWORD=", "APP_SECRET_KEY=", "/Users/nimo", ".env\n"]
    for item in forbidden:
        require(item not in text, f"forbidden evidence content: {item}")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(f"wrote {REPORT.relative_to(ROOT)}")
    print("saas_release_evidence: PASS")


if __name__ == "__main__":
    main()
