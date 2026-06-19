#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""License seat limits for SaaS staff accounts."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_binding import bind_tenant_license_customer
from server.saas_license_cloud import LicenseCloudService
from server.saas_license_seats import active_staff_count, seats_available


def _license_service(tenant='席位物业', seats=1):
    service = LicenseCloudService.in_memory()
    service.create_customer(tenant, tenant)
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.issue_entitlement(tenant, 'property-saas-backoffice', seats=seats, expires_at='2099-12-31')
    return service


def _login(client, tenant='席位物业'):
    return client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': '席位项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })


def test_seat_helpers_count_active_tenant_staff_only():
    app = create_app()
    client = TestClient(app)
    assert _login(client).status_code == 200
    service = app.state.saas_service
    user = next(iter(service.users.values()))
    bind_tenant_license_customer(service, None, user, '席位物业')

    assert active_staff_count(service, None, user) == 1
    assert seats_available(_license_service(seats=1), service, None, user, increment=0) is True
    assert seats_available(_license_service(seats=1), service, None, user, increment=1) is False
    assert seats_available(_license_service(seats=2), service, None, user, increment=1) is True


def test_create_user_is_blocked_when_license_seats_exceeded_and_audited():
    app = create_app()
    app.state.license_service = _license_service(seats=1)
    client = TestClient(app)
    assert _login(client).status_code == 200
    user = next(iter(app.state.saas_service.users.values()))
    bind_tenant_license_customer(app.state.saas_service, None, user, '席位物业')

    response = client.post('/api/users', json={'username': 'cashier1', 'role_code': 'cashier'})

    assert response.status_code == 403
    assert response.json()['detail'] == 'license_seats_exceeded'
    logs = client.get('/api/audit-logs').json()['items']
    blocked = [item for item in logs if item['action'] == 'license.seats_exceeded']
    assert blocked, logs
    detail = blocked[-1]['detail']
    assert detail['module'] == 'user.create'
    assert detail['licensed_seats'] == 1
    assert detail['active_staff_count'] == 1
    assert 'tenant_id' not in str(detail)
    assert 'project_id' not in str(detail)


def test_create_user_allowed_when_license_has_available_seats():
    app = create_app()
    app.state.license_service = _license_service(seats=2)
    client = TestClient(app)
    assert _login(client).status_code == 200
    user = next(iter(app.state.saas_service.users.values()))
    bind_tenant_license_customer(app.state.saas_service, None, user, '席位物业')

    response = client.post('/api/users', json={'username': 'cashier1', 'role_code': 'cashier'})

    assert response.status_code == 200
    assert response.json()['item']['username'] == 'cashier1'


def test_enable_user_is_blocked_when_seats_are_full_but_disable_is_allowed():
    app = create_app()
    app.state.license_service = _license_service(seats=2)
    client = TestClient(app)
    assert _login(client).status_code == 200
    user = next(iter(app.state.saas_service.users.values()))
    bind_tenant_license_customer(app.state.saas_service, None, user, '席位物业')
    created = client.post('/api/users', json={'username': 'cashier1', 'role_code': 'cashier'}).json()['item']
    assert client.post(f"/api/users/{created['id']}/active", json={'is_active': False}).status_code == 200
    app.state.license_service = _license_service(seats=1)

    response = client.post(f"/api/users/{created['id']}/active", json={'is_active': True})

    assert response.status_code == 403
    assert response.json()['detail'] == 'license_seats_exceeded'


def test_license_seat_limit_check_script_is_in_release_gate():
    script = Path('scripts/saas_license_seat_limit_check.py')
    assert script.exists(), 'missing SaaS license seat limit check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_seat_limit_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_seat_limit_check.py' in gate
