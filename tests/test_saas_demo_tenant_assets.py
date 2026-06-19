#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS demo tenant acceptance drill assets."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "saas_demo_tenant_drill.py"
DOC = ROOT / "docs" / "saas-demo-tenant-drill.md"


def test_demo_tenant_drill_script_passes_and_reports_full_workflow():
    assert SCRIPT.exists()
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True, check=False, timeout=60
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for item in [
        "PASS demo tenant login",
        "PASS demo charge targets",
        "PASS demo fee types",
        "PASS demo bill generation",
        "PASS demo bill approval",
        "PASS demo payments",
        "PASS demo report totals",
        "PASS demo exports",
        "PASS demo backup restore drill",
        "PASS demo tenant isolation",
        "saas_demo_tenant_drill: PASS",
    ]:
        assert item in result.stdout


def test_demo_tenant_drill_document_covers_safe_sample_boundary():
    assert DOC.exists()
    text = DOC.read_text(encoding="utf-8")
    for item in [
        "SaaS 样例客户验收演练",
        "脱敏样例数据",
        "样例物业公司",
        "客户上传数据与系统自身数据隔离",
        "租户隔离",
        "创建项目",
        "收费对象",
        "收费项目",
        "账单生成",
        "账单审核",
        "收款登记",
        "对账报表",
        "导出",
        "备份恢复演练",
        "scripts/saas_demo_tenant_drill.py",
    ]:
        assert item in text
    for forbidden in ["POSTGRES_PASSWORD=", "APP_SECRET_KEY=", "/Users/nimo", "真实客户"]:
        assert forbidden not in text


def test_acceptance_and_deploy_pages_link_demo_drill():
    acceptance = (ROOT / "server" / "saas_acceptance_pages.py").read_text(encoding="utf-8")
    deploy = (ROOT / "server" / "saas_deploy_pages.py").read_text(encoding="utf-8")
    for text in [acceptance, deploy]:
        assert "scripts/saas_demo_tenant_drill.py" in text
        assert "docs/saas-demo-tenant-drill.md" in text
        assert "样例客户验收演练" in text


def test_deploy_assets_include_demo_drill():
    deploy = (ROOT / "server" / "saas_deploy.py").read_text(encoding="utf-8")
    assert "scripts/saas_demo_tenant_drill.py" in deploy
    assert "docs/saas-demo-tenant-drill.md" in deploy
