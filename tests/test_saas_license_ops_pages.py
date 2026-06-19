#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Platform license operations page for SaaS commercial admin."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_cloud import LicenseCloudService
from server.saas_license_ops_pages import build_license_ops_rows


def _license_service():
    service = LicenseCloudService.in_memory()
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    for code, seats in [('甲方物业', 2), ('乙方物业', 1)]:
        service.create_customer(code, code)
        service.issue_entitlement(code, 'property-saas-backoffice', seats=seats, expires_at='2099-12-31')
    return service


def _login(client, tenant, role='system_admin'):
    return client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': f'{tenant}项目',
        'username': 'admin',
        'role_code': role,
    })


def test_license_ops_rows_show_status_seats_and_risk_without_internal_fields():
    app = create_app()
    client = TestClient(app)
    app.state.license_service = _license_service()
    assert _login(client, '甲方物业').status_code == 200
    assert client.post('/api/users', json={'username': 'cashier1', 'role_code': 'cashier'}).status_code == 200
    assert _login(client, '乙方物业').status_code == 200

    rows = build_license_ops_rows(app.state.saas_service, None, app.state.license_service)

    assert len(rows) == 2
    alpha = next(row for row in rows if row['tenant_name'] == '甲方物业')
    beta = next(row for row in rows if row['tenant_name'] == '乙方物业')
    assert alpha['status_label'] == '已授权'
    assert alpha['licensed_seats'] == 2
    assert alpha['active_staff_count'] == 2
    assert alpha['risk_label'] == '正常'
    assert beta['licensed_seats'] == 1
    assert beta['active_staff_count'] == 1
    assert set(alpha).isdisjoint({'tenant_id', 'project_id', 'license_database_url', 'business_database_url'})


def test_platform_admin_can_view_license_ops_page_but_tenant_admin_cannot():
    app = create_app()
    app.state.license_service = _license_service()
    setup = TestClient(app)
    assert _login(setup, '甲方物业').status_code == 200
    assert setup.post('/api/users', json={'username': 'cashier1', 'role_code': 'cashier'}).status_code == 200

    platform = TestClient(app)
    assert _login(platform, '平台运营', role='platform_admin').status_code == 200
    page = platform.get('/backoffice/license-ops')
    assert page.status_code == 200
    for text in ['授权状态运维', '甲方物业', '乙方物业', '已授权', '席位使用', '超限风险']:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', 'property_license_cloud', 'property_saas']:
        assert hidden not in page.text

    tenant_admin = TestClient(app)
    assert _login(tenant_admin, '甲方物业').status_code == 200
    denied = tenant_admin.get('/backoffice/license-ops')
    assert denied.status_code == 403


def test_license_ops_page_check_script_is_in_release_gate():
    script = Path('scripts/saas_license_ops_page_check.py')
    assert script.exists(), 'missing SaaS license ops page check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_ops_page_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_ops_page_check.py' in gate
