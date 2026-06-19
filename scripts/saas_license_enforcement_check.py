#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check SaaS license enforcement for write actions."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_cloud import LicenseCloudService
from server.saas_license_status import license_allows_write


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def login(client):
    return client.post('/api/auth/login', json={'tenant_name': '授权检查物业', 'project_name': '授权检查项目', 'username': 'admin', 'role_code': 'system_admin'})


def active_service():
    service = LicenseCloudService.in_memory()
    service.create_customer('授权检查物业', '授权检查物业')
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.issue_entitlement('授权检查物业', 'property-saas-backoffice', seats=3, expires_at='2099-12-31')
    return service


def main():
    require(license_allows_write(active_service(), '授权检查物业') is True, 'active license should allow write')
    require(license_allows_write(LicenseCloudService.in_memory(), '授权检查物业') is False, 'missing license should block write')
    app = create_app()
    app.state.license_service = LicenseCloudService.in_memory()
    client = TestClient(app)
    require(login(client).status_code == 200, 'login failed')
    page = client.get('/backoffice')
    require('授权限制' in page.text, 'restriction banner missing')
    denied = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5, 'billing_mode': 'area'})
    require(denied.status_code == 403 and denied.json().get('detail') == 'license_required', 'unlicensed write not blocked')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', 'property_license_cloud', 'property_saas']:
        require(forbidden not in page.text, f'page leaks forbidden field: {forbidden}')
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    require('scripts/saas_license_enforcement_check.py' in gate, 'release gate missing license enforcement check')
    print('saas_license_enforcement_check: PASS')


if __name__ == '__main__':
    main()
