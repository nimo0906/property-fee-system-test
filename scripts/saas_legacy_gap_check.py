#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check legacy desktop to SaaS business migration gap plan."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/saas-legacy-business-migration-gap.md"
DESKTOP_MODULES = [
    "rooms.py", "owners.py", "fees.py", "billing_engine.py", "bill_generation.py",
    "auto_billing.py", "payments.py", "payment_ledger.py", "bill_receipt.py",
    "bill_print.py", "bill_export.py", "reports.py", "reports_exports.py",
    "import_templates.py", "meter.py", "parking.py", "merchant_contracts.py",
    "contract_amendments.py", "invoices.py",
]
SAAS_MODULES = [
    "saas_charge_target_pages.py", "saas_fee_type_pages.py", "saas_bill_pages.py",
    "saas_billing_api.py", "saas_payment_pages.py", "saas_report_pages.py",
    "saas_import_pages.py", "saas_repository.py", "saas_service.py",
]
REQUIRED_TERMS = [
    "原桌面版业务能力到 SaaS 云端版迁移差距清单", "不是重做一套系统", "原有物业收费系统直接转化成云端商业产品",
    "收费对象", "业主", "房间", "收费项目", "计费规则", "批量出账", "自动出账", "收款", "欠费", "收据", "打印", "导出", "报表", "导入模板",
    "水电表抄表", "停车费", "商户档案", "铺位", "商户合同", "合同变更", "发票", "迁移优先级 P0", "迁移优先级 P1", "迁移优先级 P2",
    "桌面版保持稳定", "云端版必须多租户隔离", "腾讯云", "阿里云", "房间/铺位与业主绑定", "业主档案 API", "P0-1 已开始落地",
]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    require(DOC.exists(), "missing migration gap document")
    text = DOC.read_text(encoding="utf-8")
    for term in REQUIRED_TERMS:
        require(term in text, f"missing term: {term}")
    for forbidden in ["POSTGRES_PASSWORD=", "APP_SECRET_KEY=", "/Users/nimo"]:
        require(forbidden not in text, f"forbidden term: {forbidden}")
    missing_desktop = [name for name in DESKTOP_MODULES if not (ROOT / "server" / name).exists()]
    missing_saas = [name for name in SAAS_MODULES if not (ROOT / "server" / name).exists()]
    require(not missing_desktop, f"missing desktop_modules: {missing_desktop}")
    require(not missing_saas, f"missing saas_modules: {missing_saas}")
    print(f"desktop_modules={len(DESKTOP_MODULES)}")
    print(f"saas_modules={len(SAAS_MODULES)}")
    print("P0=收费核心迁移")
    print("P1=业务扩展迁移")
    print("P2=上线后增强")
    print("saas_legacy_gap_check: PASS")


if __name__ == "__main__":
    main()
