#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production acceptance result page for SaaS delivery operators."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_acceptance_page_check.py'
SCRIPT_REF = 'scripts/saas_production_acceptance_page_check.py'


def _login(client):
    return client.post('/api/auth/login', json={
        'tenant_name': '生产验收页面物业',
        'project_name': '生产验收页面项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })


def test_production_acceptance_page_shows_all_delivery_evidence_without_sensitive_fields():
    client = TestClient(create_app())
    assert _login(client).status_code == 200
    page = client.get('/backoffice/production-acceptance')
    assert page.status_code == 200
    required = [
        '生产验收结果中心',
        '一键验收总入口',
        'scripts/saas_production_acceptance_gate.py',
        '验收结果留档文件',
        'release/saas-production-acceptance-result.md',
        '上线证据报告',
        'release/saas-release-evidence.md',
        '租户隔离证据',
        'release/saas-isolation-evidence.md',
        '首租户冒烟说明',
        'scripts/saas_production_first_tenant_smoke.py',
        '客户上传数据与系统自身数据隔离',
        '失败即停止交付',
    ]
    for item in required:
        assert item in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo']:
        assert hidden not in page.text


def test_production_acceptance_page_is_linked_from_deploy_checklist_and_acceptance_dashboard():
    client = TestClient(create_app())
    assert _login(client).status_code == 200
    deploy = client.get('/backoffice/deploy-checklist')
    acceptance = client.get('/backoffice/acceptance')
    assert deploy.status_code == 200
    assert acceptance.status_code == 200
    for page in [deploy.text, acceptance.text]:
        assert '/backoffice/production-acceptance' in page
        assert '生产验收结果中心' in page
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in deploy.text
        assert hidden not in acceptance.text


def test_production_acceptance_page_check_is_registered_and_passes():
    assert SCRIPT.exists(), 'missing production acceptance page check script'
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for item in [
        'PASS production acceptance result page',
        'PASS production acceptance result page links',
        'PASS production acceptance result page registry',
        'saas_production_acceptance_page_check: PASS',
    ]:
        assert item in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
