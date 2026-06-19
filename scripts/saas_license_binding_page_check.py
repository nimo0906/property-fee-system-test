#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check platform license tenant binding page action."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_binding import license_customer_code_for_user
from server.saas_license_cloud import LicenseCloudService


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    app = create_app()
    service = LicenseCloudService.in_memory()
    service.create_customer('cust-bind-page', '绑定页客户')
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.issue_entitlement('cust-bind-page', 'property-saas-backoffice', seats=2, expires_at='2099-12-31')
    app.state.license_service = service
    tenant_client = TestClient(app)
    require(tenant_client.post('/api/auth/login', json={'tenant_name': '绑定页物业', 'project_name': '绑定页项目', 'username': 'admin', 'role_code': 'system_admin'}).status_code == 200, 'tenant login failed')
    tenant_user = next(iter(app.state.saas_service.users.values()))
    platform = TestClient(app)
    require(platform.post('/api/auth/login', json={'tenant_name': '平台运营', 'project_name': '平台项目', 'username': 'admin', 'role_code': 'platform_admin'}).status_code == 200, 'platform login failed')
    page = platform.get('/backoffice/license-ops')
    require('绑定授权客户' in page.text, 'binding form missing')
    response = platform.post('/backoffice/license-ops/bind', data={'tenant_name': '绑定页物业', 'customer_code': 'cust-bind-page'}, follow_redirects=False)
    require(response.status_code == 303, 'binding post failed')
    require(license_customer_code_for_user(app.state.saas_service, None, tenant_user) == 'cust-bind-page', 'binding not saved')
    logs = tenant_client.get('/api/audit-logs').json()['items']
    require(any(item['action'] == 'license.tenant_bind' for item in logs), 'binding audit missing')
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    require('scripts/saas_license_binding_page_check.py' in gate, 'release gate missing license binding page check')
    print('saas_license_binding_page_check: PASS')


if __name__ == '__main__':
    main()
