#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS backoffice reads license result without mixing license and business data."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_binding import bind_tenant_license_customer
from server.saas_license_cloud import LicenseCloudService
from server.saas_license_status import build_saas_license_status


def test_saas_license_status_uses_only_license_result_fields():
    service = LicenseCloudService.in_memory()
    service.create_customer('tenant-license-alpha', '甲方物业公司')
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.issue_entitlement('tenant-license-alpha', 'property-saas-backoffice', seats=30, expires_at='2099-12-31')

    result = build_saas_license_status(service, 'tenant-license-alpha')

    assert result == {
        'allowed': True,
        'status': 'active',
        'customer_code': 'tenant-license-alpha',
        'product_code': 'property-saas-backoffice',
        'seats': 30,
        'expires_at': '2099-12-31',
    }
    assert 'tenant_id' not in result
    assert 'project_id' not in result
    assert 'business_database_url' not in result
    assert 'license_database_url' not in result


def test_saas_backoffice_home_shows_sanitized_license_status():
    license_service = LicenseCloudService.in_memory()
    license_service.create_customer('工单拆分物业', '工单拆分物业')
    license_service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    license_service.issue_entitlement('工单拆分物业', 'property-saas-backoffice', seats=18, expires_at='2099-12-31')
    app = create_app()
    app.state.license_service = license_service
    client = TestClient(app)

    login = client.post('/api/auth/login', json={
        'tenant_name': '工单拆分物业',
        'project_name': '工单拆分项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    user = next(iter(app.state.saas_service.users.values()))
    bind_tenant_license_customer(app.state.saas_service, None, user, '工单拆分物业')

    page = client.get('/backoffice')

    assert page.status_code == 200
    for text in ['授权状态', '已授权', '席位 18', '到期 2099-12-31']:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', 'property_license_cloud', 'property_saas']:
        assert hidden not in page.text


def test_saas_license_status_check_script_is_in_release_gate():
    script = Path('scripts/saas_license_status_integration_check.py')
    assert script.exists(), 'missing SaaS license status integration check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_status_integration_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_status_integration_check.py' in gate
