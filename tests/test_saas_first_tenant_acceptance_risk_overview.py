#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant acceptance risk overview on delivery and commercial pages."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_first_tenant_acceptance_pages import ITEMS


def _client(tenant='风险总览物业', project='风险总览项目'):
    client = TestClient(create_app())
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': 'platform_admin',
        'role_code': 'platform_admin',
    })
    assert response.status_code == 200
    return client


def _save_full_acceptance(client):
    response = client.post('/backoffice/first-tenant-acceptance', data={
        'items': ITEMS,
        'operator_name': '实施A',
        'customer_signer': '客户B',
        'notes': '全部完成',
    }, follow_redirects=True)
    assert response.status_code == 200


def _assert_public_page(html):
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo']:
        assert hidden not in html


def test_delivery_package_shows_acceptance_risk_before_record_exists():
    client = _client('风险总览未完成', '交付包项目')
    page = client.get('/backoffice/first-tenant-delivery-package')
    assert page.status_code == 200
    for text in ['验收风险', '完成项不足', '金额配置复核未完成', '上线前请勿签收', '/backoffice/first-tenant-acceptance']:
        assert text in page.text
    _assert_public_page(page.text)


def test_delivery_package_shows_risk_cleared_after_full_acceptance():
    client = _client('风险总览已完成', '交付包项目')
    _save_full_acceptance(client)
    page = client.get('/backoffice/first-tenant-delivery-package')
    assert page.status_code == 200
    assert '验收风险已解除' in page.text
    assert '全部验收项已完成' in page.text
    _assert_public_page(page.text)


def test_commercial_acceptance_page_shows_first_tenant_risk_status():
    client = _client('商业验收风险总览', '商业验收项目')
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    assert '验收风险' in page.text
    assert '金额配置复核未完成' in page.text
    _assert_public_page(page.text)

    _save_full_acceptance(client)
    cleared = client.get('/backoffice/acceptance')
    assert cleared.status_code == 200
    assert '验收风险已解除' in cleared.text
    assert '全部验收项已完成' in cleared.text
    _assert_public_page(cleared.text)


def test_acceptance_risk_overview_check_script_is_in_release_assets():
    script = 'scripts/saas_first_tenant_acceptance_risk_overview_check.py'
    result = subprocess.run([sys.executable, script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
    assert result.returncode == 0, result.stdout
    for path in [
        'scripts/saas_release_gate.py',
        'scripts/saas_release_evidence.py',
        'server/saas_deploy.py',
        'server/saas_commercial_readiness.py',
    ]:
        assert script in Path(path).read_text(encoding='utf-8')
