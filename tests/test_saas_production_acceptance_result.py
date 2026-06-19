#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sanitized production acceptance result archive for SaaS delivery."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_acceptance_result.py'
REPORT = ROOT / 'release/saas-production-acceptance-result.md'
SCRIPT_REF = 'scripts/saas_production_acceptance_result.py'
REPORT_REF = 'release/saas-production-acceptance-result.md'


def test_acceptance_result_script_generates_sanitized_report():
    assert SCRIPT.exists(), 'missing acceptance result script'
    if REPORT.exists():
        REPORT.unlink()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--operator', '实施人员手填', '--domain', 'your-domain.example.com'],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_production_acceptance_result: PASS' in result.stdout
    assert REPORT.exists()
    text = REPORT.read_text(encoding='utf-8')
    required = [
        'SaaS 生产上线验收结果留档',
        '执行时间',
        '执行人：实施人员手填',
        '服务器域名：your-domain.example.com',
        'scripts/saas_production_env_file_check.py',
        'scripts/saas_production_precheck.py',
        'scripts/saas_production_runtime_check.py',
        'scripts/saas_production_first_tenant_smoke.py',
        'scripts/saas_isolation_evidence.py',
        'scripts/saas_release_evidence.py',
        '首租户业务冒烟结果',
        '租户隔离结果',
        '备份/证据文件位置',
        '客户签收人',
        '实施人员签字',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo', 'tenant_id', 'project_id']:
        assert forbidden not in text


def test_acceptance_gate_generates_result_report_in_dry_run():
    if REPORT.exists():
        REPORT.unlink()
    result = subprocess.run(
        [sys.executable, 'scripts/saas_production_acceptance_gate.py', '--dry-run'],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'RUN scripts/saas_production_acceptance_result.py' in result.stdout
    assert 'saas_production_acceptance_result: PASS' in result.stdout
    assert REPORT.exists()
    text = REPORT.read_text(encoding='utf-8')
    assert 'SaaS 生产上线验收结果留档' in text
    assert 'PASS' in text


def test_acceptance_result_is_registered_in_release_assets_docs_and_page():
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'scripts/saas_production_precheck.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
        ROOT / 'docs/saas-production-deployment-commands.md',
    ]:
        text = path.read_text(encoding='utf-8')
        assert SCRIPT_REF in text or REPORT_REF in text, f'missing acceptance result reference in {path}'

    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '验收留档物业',
        'project_name': '验收留档项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/deploy-checklist')
    assert page.status_code == 200
    for item in [
        '生产验收结果留档',
        'scripts/saas_production_acceptance_result.py',
        'release/saas-production-acceptance-result.md',
        '执行人、服务器域名、PASS/FAIL、客户签收人',
    ]:
        assert item in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
