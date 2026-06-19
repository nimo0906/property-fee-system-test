#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check SaaS license seat limits for staff accounts."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_cloud import LicenseCloudService


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def license_service(seats):
    service = LicenseCloudService.in_memory()
    service.create_customer('席位检查物业', '席位检查物业')
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.issue_entitlement('席位检查物业', 'property-saas-backoffice', seats=seats, expires_at='2099-12-31')
    return service


def main():
    app = create_app()
    app.state.license_service = license_service(1)
    client = TestClient(app)
    login = client.post('/api/auth/login', json={'tenant_name': '席位检查物业', 'project_name': '席位检查项目', 'username': 'admin', 'role_code': 'system_admin'})
    require(login.status_code == 200, 'login failed')
    blocked = client.post('/api/users', json={'username': 'cashier1', 'role_code': 'cashier'})
    require(blocked.status_code == 403 and blocked.json().get('detail') == 'license_seats_exceeded', 'seat limit not enforced')
    logs = client.get('/api/audit-logs').json()['items']
    require(any(item['action'] == 'license.seats_exceeded' for item in logs), 'missing seat limit audit')
    detail_text = str([item for item in logs if item['action'] == 'license.seats_exceeded'][-1]['detail'])
    for forbidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        require(forbidden not in detail_text, f'audit leaks forbidden field: {forbidden}')
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    require('scripts/saas_license_seat_limit_check.py' in gate, 'release gate missing license seat limit check')
    print('saas_license_seat_limit_check: PASS')


if __name__ == '__main__':
    main()
