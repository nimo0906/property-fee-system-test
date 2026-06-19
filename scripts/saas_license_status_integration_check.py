#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check SaaS backoffice license status integration stays sanitized."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_cloud import LicenseCloudService
from server.saas_license_status import build_saas_license_status


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    license_service = LicenseCloudService.in_memory()
    license_service.create_customer('检查物业', '检查物业')
    license_service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    license_service.issue_entitlement('检查物业', 'property-saas-backoffice', seats=9, expires_at='2099-12-31')
    status = build_saas_license_status(license_service, '检查物业')
    require(status['allowed'] is True and status['seats'] == 9, 'license status not active')
    for forbidden in ['tenant_id', 'project_id', 'business_database_url', 'license_database_url']:
        require(forbidden not in status, f'status leaks forbidden field: {forbidden}')
    app = create_app()
    app.state.license_service = license_service
    client = TestClient(app)
    login = client.post('/api/auth/login', json={'tenant_name': '检查物业', 'project_name': '检查项目', 'username': 'admin', 'role_code': 'system_admin'})
    require(login.status_code == 200, 'login failed')
    page = client.get('/backoffice')
    require(page.status_code == 200, 'backoffice failed')
    for item in ['授权状态', '已授权', '席位 9', '到期 2099-12-31']:
        require(item in page.text, f'page missing: {item}')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', 'property_license_cloud', 'property_saas']:
        require(forbidden not in page.text, f'page leaks forbidden field: {forbidden}')
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    require('scripts/saas_license_status_integration_check.py' in gate, 'release gate missing license status integration check')
    print('saas_license_status_integration_check: PASS')


if __name__ == '__main__':
    main()
