#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS phase 1 closure report and check assets."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "saas-phase-1-closure-report.md"
CHECK = ROOT / "scripts" / "saas_phase1_closure_check.py"


REQUIRED_REPORT_TERMS = [
    "第一阶段收口",
    "员工后台云端化",
    "登录、租户、角色权限",
    "收费对象",
    "收费项目",
    "账单生成",
    "账单审核",
    "收款登记",
    "收据",
    "导出",
    "对账报表",
    "数据导入",
    "审计日志",
    "备份恢复",
    "租户隔离",
    "客户上传数据与系统自身数据隔离",
    "业主端 H5 后置",
    "微信/支付宝真实支付后置",
    "授权云服务后台后置",
]

FORBIDDEN_REPORT_TERMS = [
    "POSTGRES_PASSWORD=",
    "APP_SECRET_KEY=",
    "/Users/nimo",
]


def test_phase1_closure_report_exists_and_covers_scope():
    assert REPORT.exists()
    text = REPORT.read_text(encoding="utf-8")
    for term in REQUIRED_REPORT_TERMS:
        assert term in text
    for term in FORBIDDEN_REPORT_TERMS:
        assert term not in text


def test_phase1_closure_check_script_passes():
    assert CHECK.exists()
    result = subprocess.run(
        [sys.executable, str(CHECK)], cwd=ROOT, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "saas_phase1_closure_check: PASS" in result.stdout


def test_acceptance_page_links_phase1_closure_assets():
    page = (ROOT / "server" / "saas_acceptance_pages.py").read_text(encoding="utf-8")
    assert "docs/saas-phase-1-closure-report.md" in page
    assert "scripts/saas_phase1_closure_check.py" in page
    assert "第一阶段收口" in page


def test_deploy_assets_include_phase1_closure_check():
    deploy = (ROOT / "server" / "saas_deploy.py").read_text(encoding="utf-8")
    assert "scripts/saas_phase1_closure_check.py" in deploy
    assert "docs/saas-phase-1-closure-report.md" in deploy


def test_acceptance_page_renders_phase1_closure_entry():
    from fastapi.testclient import TestClient
    from server.saas_app import create_app

    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '收口验收物业',
        'project_name': '收口验收项目',
        'username': 'system_admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    assert '第一阶段收口' in page.text
    assert 'scripts/saas_phase1_closure_check.py' in page.text
    assert 'docs/saas-phase-1-closure-report.md' in page.text
