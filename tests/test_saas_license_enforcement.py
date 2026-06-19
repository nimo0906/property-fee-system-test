#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""License enforcement blocks write actions without mixing business data."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_binding import bind_tenant_license_customer
from server.saas_license_cloud import LicenseCloudService
from server.saas_license_status import license_allows_write


def _login(client, tenant='授权限制物业'):
    return client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': '授权限制项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })


def _active_license_service(tenant='授权限制物业', expires_at='2099-12-31'):
    service = LicenseCloudService.in_memory()
    service.create_customer(tenant, tenant)
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.issue_entitlement(tenant, 'property-saas-backoffice', seats=10, expires_at=expires_at)
    return service


def test_license_policy_allows_only_active_license_to_write():
    active = _active_license_service()
    missing = LicenseCloudService.in_memory()
    expired = _active_license_service(expires_at='2000-01-01')

    assert license_allows_write(active, '授权限制物业') is True
    assert license_allows_write(missing, '授权限制物业') is False
    assert license_allows_write(expired, '授权限制物业') is False


def test_unlicensed_tenant_can_read_but_cannot_create_fee_type():
    app = create_app()
    app.state.license_service = LicenseCloudService.in_memory()
    client = TestClient(app)
    assert _login(client).status_code == 200

    read_page = client.get('/backoffice')
    assert read_page.status_code == 200
    assert '授权限制' in read_page.text

    denied = client.post('/api/fee-types', json={
        'name': '物业费',
        'unit_price': 2.5,
        'billing_mode': 'area',
    })

    assert denied.status_code == 403
    assert denied.json()['detail'] == 'license_required'


def test_active_license_allows_create_fee_type():
    app = create_app()
    app.state.license_service = _active_license_service()
    client = TestClient(app)
    assert _login(client).status_code == 200
    user = next(iter(app.state.saas_service.users.values()))
    bind_tenant_license_customer(app.state.saas_service, None, user, '授权限制物业')

    response = client.post('/api/fee-types', json={
        'name': '物业费',
        'unit_price': 2.5,
        'billing_mode': 'area',
    })

    assert response.status_code == 200
    assert response.json()['item']['name'] == '物业费'


def test_license_restriction_banner_is_sanitized():
    app = create_app()
    app.state.license_service = LicenseCloudService.in_memory()
    client = TestClient(app)
    assert _login(client).status_code == 200

    page = client.get('/backoffice')

    assert page.status_code == 200
    for text in ['授权状态', '未授权', '授权限制', '已限制出账、收费项目、收费对象、导入确认和备份创建等写入操作']:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', 'property_license_cloud', 'property_saas']:
        assert hidden not in page.text


def test_license_enforcement_check_script_is_in_release_gate():
    script = Path('scripts/saas_license_enforcement_check.py')
    assert script.exists(), 'missing SaaS license enforcement check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_enforcement_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_enforcement_check.py' in gate
