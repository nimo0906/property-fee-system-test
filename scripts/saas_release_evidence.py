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
    "scripts/saas_preflight_check.py",
    "scripts/saas_ops_check.py",
    "scripts/saas_acceptance_check.py",
    "scripts/saas_phase1_closure_check.py",
    "scripts/saas_demo_tenant_drill.py",
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

验收重点：租户隔离；客户上传数据与系统自身数据隔离；备份、日志和系统文件不与租户业务文件混放。

## 业务闭环证据

- 登录、租户、角色权限已由 `scripts/saas_acceptance_check.py` 覆盖。
- 收费对象、收费项目、账单生成、账单审核、收款登记、对账报表、导出已由 `scripts/saas_acceptance_check.py` 和 `scripts/saas_demo_tenant_drill.py` 覆盖。
- 备份恢复演练、管理员密码重置流程、日志轮转由 `scripts/saas_ops_check.py` 覆盖。
- 第一阶段范围和后置边界由 `scripts/saas_phase1_closure_check.py` 覆盖。

## 后置范围

{postponed_rows}

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
