#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production delivery overview page for on-site operators."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_delivery_overview_check.py'
SCRIPT_REF = 'scripts/saas_production_delivery_overview_check.py'


def _login(client):
    response = client.post('/api/auth/login', json={
        'tenant_name': '生产交付总览物业',
        'project_name': '生产交付总览项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200


def _assert_safe(text):
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo', '.env']:
        assert hidden not in text


def test_production_delivery_overview_orders_all_on_site_delivery_steps():
    client = TestClient(create_app())
    _login(client)
    page = client.get('/backoffice/production-delivery')
    assert page.status_code == 200
    required = [
        '生产交付总览',
        '现场实施顺序',
        '1. 生产部署自检',
        '2. 首租户业务冒烟',
        '3. 生产一键验收',
        '4. 生产验收结果中心',
        '5. 下载交付证据包',
        '6. 填写生产验收签收',
        '7. 查看签收历史',
        '8. 备份恢复覆盖核验',
        '/backoffice/deploy-checklist',
        '/backoffice/production-acceptance',
        '/backoffice/production-acceptance/evidence-package.zip',
        '/backoffice/production-acceptance/signoff',
        '/backoffice/backups',
        'scripts/saas_production_precheck.py',
        'scripts/saas_production_first_tenant_smoke.py',
        'scripts/saas_production_acceptance_gate.py',
        '客户上传数据与系统自身数据隔离',
        '业务数据不进入授权云服务',
    ]
    for item in required:
        assert item in page.text
    _assert_safe(page.text)


def test_production_delivery_overview_is_linked_from_main_delivery_pages():
    client = TestClient(create_app())
    _login(client)
    pages = [
        client.get('/backoffice'),
        client.get('/backoffice/deploy-checklist'),
        client.get('/backoffice/production-acceptance'),
        client.get('/backoffice/acceptance'),
    ]
    for response in pages:
        assert response.status_code == 200
        assert '/backoffice/production-delivery' in response.text
        assert '生产交付总览' in response.text


def test_production_delivery_overview_check_script_is_registered_and_passes():
    assert SCRIPT.exists(), 'missing production delivery overview check script'
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
    assert 'saas_production_delivery_overview_check: PASS' in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
