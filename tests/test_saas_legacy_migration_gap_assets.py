#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy desktop to SaaS migration gap assets."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "saas-legacy-business-migration-gap.md"
SCRIPT = ROOT / "scripts" / "saas_legacy_gap_check.py"

REQUIRED_TERMS = [
    "原桌面版业务能力到 SaaS 云端版迁移差距清单",
    "不是重做一套系统",
    "原有物业收费系统直接转化成云端商业产品",
    "收费对象",
    "业主",
    "房间",
    "收费项目",
    "计费规则",
    "批量出账",
    "自动出账",
    "收款",
    "欠费",
    "收据",
    "打印",
    "导出",
    "报表",
    "导入模板",
    "水电表抄表",
    "停车费",
    "商户档案",
    "铺位",
    "商户合同",
    "合同变更",
    "发票",
    "迁移优先级 P0",
    "迁移优先级 P1",
    "迁移优先级 P2",
    "桌面版保持稳定",
    "云端版必须多租户隔离",
    "腾讯云",
    "阿里云",
]


def test_legacy_migration_gap_document_exists_and_covers_core_business():
    assert DOC.exists()
    text = DOC.read_text(encoding="utf-8")
    for term in REQUIRED_TERMS:
        assert term in text
    for forbidden in ["POSTGRES_PASSWORD=", "APP_SECRET_KEY=", "/Users/nimo"]:
        assert forbidden not in text


def test_legacy_gap_check_script_passes():
    assert SCRIPT.exists()
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True, check=False, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "saas_legacy_gap_check: PASS" in result.stdout
    for item in ["P0", "P1", "P2", "desktop_modules", "saas_modules"]:
        assert item in result.stdout


def test_backoffice_and_release_gate_link_legacy_gap_check():
    files = [
        ROOT / "server" / "saas_backoffice_pages.py",
        ROOT / "server" / "saas_acceptance_pages.py",
        ROOT / "scripts" / "saas_release_gate.py",
        ROOT / "scripts" / "saas_release_evidence.py",
        ROOT / "server" / "saas_deploy.py",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "scripts/saas_legacy_gap_check.py" in text
        assert "saas-legacy-business-migration-gap.md" in text or path.name == "saas_release_gate.py"


def test_legacy_gap_doc_explains_direct_migration_map_not_rebuild():
    text = DOC.read_text(encoding='utf-8')
    for term in [
        '本地端不是重新做一套，而是按模块移植到云端',
        '本地端已有能力',
        '本地模块',
        '云端承接模块',
        '移植状态',
        '下一步动作',
        'rooms.py / owners.py',
        'saas_charge_target_pages.py / saas_owner_pages.py',
        'billing_engine.py / bill_generation.py',
        'saas_batch_billing.py / saas_bill_pages.py',
        'payments.py / payment_ledger.py',
        'saas_payment_pages.py',
        'reports.py / reports_exports.py',
        'saas_report_pages.py',
        'import_templates.py',
        'saas_import_pages.py',
    ]:
        assert term in text
    for hidden in ['tenant_id=', 'project_id=', 'POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo', '.env']:
        assert hidden not in text
