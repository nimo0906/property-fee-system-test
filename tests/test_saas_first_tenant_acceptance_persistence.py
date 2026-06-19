#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant acceptance records persist in system-scoped storage."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_first_tenant_acceptance_pages import ITEMS
from server.saas_first_tenant_acceptance_store import FirstTenantAcceptanceStore


def _login(client, tenant='验收持久化物业', project='验收持久化项目'):
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': 'platform_admin',
        'role_code': 'platform_admin',
    })
    assert response.status_code == 200


def _assert_safe(text):
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo']:
        assert hidden not in text


def test_acceptance_records_survive_service_restart_from_system_store(tmp_path):
    store = FirstTenantAcceptanceStore(tmp_path)
    client = TestClient(create_app(acceptance_store=store))
    _login(client)
    saved = client.post('/backoffice/first-tenant-acceptance', data={
        'items': ITEMS,
        'operator_name': '实施A',
        'customer_signer': '客户B',
        'notes': '重启后仍可读取',
    }, follow_redirects=True)
    assert saved.status_code == 200
    assert '15 / 15' in saved.text
    assert (tmp_path / 'system' / 'first_tenant_acceptance' / 'records.json').exists()

    restarted = TestClient(create_app(acceptance_store=store))
    _login(restarted)
    page = restarted.get('/backoffice/first-tenant-acceptance')
    assert page.status_code == 200
    assert '实施A' in page.text
    assert '客户B' in page.text
    assert '重启后仍可读取' in page.text
    assert '15 / 15' in page.text
    assert '验收风险已解除' in page.text
    _assert_safe(page.text)


def test_acceptance_store_is_system_scoped_and_tenant_isolated(tmp_path):
    store = FirstTenantAcceptanceStore(tmp_path)
    client = TestClient(create_app(acceptance_store=store))
    _login(client, '验收持久化A', '项目A')
    client.post('/backoffice/first-tenant-acceptance', data={
        'items': ITEMS,
        'operator_name': '实施A',
        'customer_signer': '客户A',
        'notes': 'A公司验收',
    }, follow_redirects=True)

    other = TestClient(create_app(acceptance_store=store))
    _login(other, '验收持久化B', '项目B')
    other_page = other.get('/backoffice/first-tenant-acceptance')
    assert other_page.status_code == 200
    assert 'A公司验收' not in other_page.text
    assert '暂无验收记录' in other_page.text
    assert str(store.relative_path) == 'system/first_tenant_acceptance/records.json'


def test_create_app_enables_acceptance_store_from_system_files_env(tmp_path, monkeypatch):
    system_dir = tmp_path / 'system'
    monkeypatch.setenv('SAAS_SYSTEM_FILES_DIR', str(system_dir))
    client = TestClient(create_app())
    assert client.app.state.saas_service.first_tenant_acceptance_store.path == tmp_path / 'system' / 'first_tenant_acceptance' / 'records.json'


def test_acceptance_persistence_check_script_is_in_release_assets():
    script = 'scripts/saas_first_tenant_acceptance_persistence_check.py'
    result = subprocess.run([sys.executable, script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
    assert result.returncode == 0, result.stdout
    for path in [
        'scripts/saas_release_gate.py',
        'scripts/saas_release_evidence.py',
        'server/saas_deploy.py',
        'server/saas_commercial_readiness.py',
    ]:
        assert script in Path(path).read_text(encoding='utf-8')
