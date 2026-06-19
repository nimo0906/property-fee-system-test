#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check platform license operations page."""

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


def main():
    app = create_app()
    service = LicenseCloudService.in_memory()
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.create_customer('授权运维检查物业', '授权运维检查物业')
    service.issue_entitlement('授权运维检查物业', 'property-saas-backoffice', seats=2, expires_at='2099-12-31')
    app.state.license_service = service
    setup = TestClient(app)
    setup.post('/api/auth/login', json={'tenant_name': '授权运维检查物业', 'project_name': '授权运维检查项目', 'username': 'admin', 'role_code': 'system_admin'})
    platform = TestClient(app)
    login = platform.post('/api/auth/login', json={'tenant_name': '平台运营', 'project_name': '平台项目', 'username': 'admin', 'role_code': 'platform_admin'})
    require(login.status_code == 200, 'platform login failed')
    page = platform.get('/backoffice/license-ops')
    require(page.status_code == 200, 'license ops page failed')
    for item in ['授权状态运维', '授权运维检查物业', '已授权', '席位使用', '超限风险']:
        require(item in page.text, f'page missing: {item}')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', 'property_license_cloud', 'property_saas']:
        require(forbidden not in page.text, f'page leaks forbidden field: {forbidden}')
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    require('scripts/saas_license_ops_page_check.py' in gate, 'release gate missing license ops page check')
    print('saas_license_ops_page_check: PASS')


if __name__ == '__main__':
    main()
