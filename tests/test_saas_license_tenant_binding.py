#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explicit binding between SaaS tenants and license customers."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_binding import bind_tenant_license_customer, license_customer_code_for_user
from server.saas_license_cloud import LicenseCloudService
from server.saas_license_status import build_saas_license_status


def _license_service(customer_code='cust-alpha', seats=3):
    service = LicenseCloudService.in_memory()
    service.create_customer(customer_code, '甲方物业授权客户')
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.issue_entitlement(customer_code, 'property-saas-backoffice', seats=seats, expires_at='2099-12-31')
    return service


def _login(client, tenant='甲方物业公司'):
    return client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': '甲方项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })


def test_bound_license_customer_code_is_used_instead_of_tenant_name():
    app = create_app()
    app.state.license_service = _license_service('cust-alpha', seats=3)
    client = TestClient(app)
    assert _login(client, tenant='甲方物业公司').status_code == 200
    user = next(iter(app.state.saas_service.users.values()))
    bind_tenant_license_customer(app.state.saas_service, None, user, 'cust-alpha')

    assert license_customer_code_for_user(app.state.saas_service, None, user) == 'cust-alpha'
    status = build_saas_license_status(app.state.license_service, license_customer_code_for_user(app.state.saas_service, None, user))
    assert status['allowed'] is True
    assert status['customer_code'] == 'cust-alpha'

    created = client.post('/api/users', json={'username': 'cashier1', 'role_code': 'cashier'})
    assert created.status_code == 200


def test_unbound_tenant_name_does_not_accidentally_match_license_customer():
    app = create_app()
    app.state.license_service = _license_service('甲方物业公司', seats=3)
    client = TestClient(app)
    assert _login(client, tenant='甲方物业公司').status_code == 200

    page = client.get('/backoffice')
    blocked = client.post('/api/users', json={'username': 'cashier1', 'role_code': 'cashier'})

    assert '未绑定授权客户' in page.text
    assert blocked.status_code == 403
    assert blocked.json()['detail'] == 'license_seats_exceeded'


def test_license_ops_page_shows_binding_status_without_internal_fields():
    app = create_app()
    app.state.license_service = _license_service('cust-alpha', seats=2)
    setup = TestClient(app)
    assert _login(setup, tenant='甲方物业公司').status_code == 200
    user = next(iter(app.state.saas_service.users.values()))
    bind_tenant_license_customer(app.state.saas_service, None, user, 'cust-alpha')

    platform = TestClient(app)
    assert platform.post('/api/auth/login', json={
        'tenant_name': '平台运营', 'project_name': '平台项目', 'username': 'admin', 'role_code': 'platform_admin'
    }).status_code == 200
    page = platform.get('/backoffice/license-ops')

    assert page.status_code == 200
    for text in ['甲方物业公司', 'cust-alpha', '已绑定', '已授权']:
        assert text in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'property_license_cloud', 'property_saas']:
        assert hidden not in page.text


def test_license_tenant_binding_check_script_is_in_release_gate():
    script = Path('scripts/saas_license_tenant_binding_check.py')
    assert script.exists(), 'missing SaaS license tenant binding check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_tenant_binding_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_tenant_binding_check.py' in gate
