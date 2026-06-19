#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check explicit SaaS tenant to license customer binding."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_binding import bind_tenant_license_customer, license_customer_code_for_user
from server.saas_license_cloud import LicenseCloudService
from server.saas_license_status import build_saas_license_status


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    app = create_app()
    license_service = LicenseCloudService.in_memory()
    license_service.create_customer('cust-bind-check', '绑定检查客户')
    license_service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    license_service.issue_entitlement('cust-bind-check', 'property-saas-backoffice', seats=2, expires_at='2099-12-31')
    app.state.license_service = license_service
    client = TestClient(app)
    login = client.post('/api/auth/login', json={'tenant_name': '绑定检查物业', 'project_name': '绑定检查项目', 'username': 'admin', 'role_code': 'system_admin'})
    require(login.status_code == 200, 'login failed')
    user = next(iter(app.state.saas_service.users.values()))
    bind_tenant_license_customer(app.state.saas_service, None, user, 'cust-bind-check')
    code = license_customer_code_for_user(app.state.saas_service, None, user)
    require(code == 'cust-bind-check', 'binding missing')
    status = build_saas_license_status(license_service, code)
    require(status.get('allowed') is True, 'bound license not active')
    page = client.get('/backoffice')
    for item in ['授权客户 cust-bind-check', '已授权']:
        require(item in page.text, f'page missing: {item}')
    for forbidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        require(forbidden not in page.text, f'page leaks forbidden field: {forbidden}')
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    require('scripts/saas_license_tenant_binding_check.py' in gate, 'release gate missing license tenant binding check')
    print('saas_license_tenant_binding_check: PASS')


if __name__ == '__main__':
    main()
