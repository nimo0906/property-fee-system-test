#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Platform UI for binding SaaS tenants to license customers."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_binding import license_customer_code_for_user
from server.saas_license_cloud import LicenseCloudService


def _license_service():
    service = LicenseCloudService.in_memory()
    service.create_customer('cust-bind-ui', '绑定页面授权客户')
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.issue_entitlement('cust-bind-ui', 'property-saas-backoffice', seats=2, expires_at='2099-12-31')
    return service


def _login(client, tenant, role='system_admin'):
    return client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': f'{tenant}项目',
        'username': 'admin',
        'role_code': role,
    })


def test_platform_admin_binds_tenant_to_license_customer_from_ops_page():
    app = create_app()
    app.state.license_service = _license_service()
    tenant_client = TestClient(app)
    assert _login(tenant_client, '绑定页面物业').status_code == 200
    tenant_user = next(iter(app.state.saas_service.users.values()))

    platform = TestClient(app)
    assert _login(platform, '平台运营', role='platform_admin').status_code == 200
    page = platform.get('/backoffice/license-ops')
    assert page.status_code == 200
    assert '绑定授权客户' in page.text

    response = platform.post('/backoffice/license-ops/bind', data={
        'tenant_name': '绑定页面物业',
        'customer_code': 'cust-bind-ui',
    }, follow_redirects=False)

    assert response.status_code == 303
    assert license_customer_code_for_user(app.state.saas_service, None, tenant_user) == 'cust-bind-ui'
    updated = platform.get('/backoffice/license-ops')
    assert 'cust-bind-ui' in updated.text
    assert '已绑定' in updated.text
    logs = tenant_client.get('/api/audit-logs').json()['items']
    assert any(item['action'] == 'license.tenant_bind' for item in logs)


def test_tenant_admin_cannot_bind_license_customer():
    app = create_app()
    app.state.license_service = _license_service()
    tenant_client = TestClient(app)
    assert _login(tenant_client, '绑定页面物业').status_code == 200

    response = tenant_client.post('/backoffice/license-ops/bind', data={
        'tenant_name': '绑定页面物业',
        'customer_code': 'cust-bind-ui',
    })

    assert response.status_code == 403


def test_license_binding_page_check_script_is_in_release_gate():
    script = Path('scripts/saas_license_binding_page_check.py')
    assert script.exists(), 'missing SaaS license binding page check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_binding_page_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_binding_page_check.py' in gate
