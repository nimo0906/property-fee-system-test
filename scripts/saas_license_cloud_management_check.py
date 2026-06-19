#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check license cloud management API and admin page."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_license_cloud import create_license_app


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    client = TestClient(create_license_app())
    require(client.post('/api/license/customers', json={'customer_code': 'cust-check', 'name': '检查客户'}).status_code == 200, 'customer create failed')
    require(client.post('/api/license/products', json={'product_code': 'property-saas-backoffice', 'name': '物业收费 SaaS 员工后台'}).status_code == 200, 'product create failed')
    require(client.post('/api/license/entitlements', json={'customer_code': 'cust-check', 'product_code': 'property-saas-backoffice', 'seats': 5, 'expires_at': '2099-12-31'}).status_code == 200, 'entitlement issue failed')
    for path in ['/api/license/customers', '/api/license/products', '/api/license/entitlements', '/api/license/audit-logs']:
        response = client.get(path)
        require(response.status_code == 200, f'api failed: {path}')
        text = str(response.json())
        for forbidden in ['tenant_id', 'project_id', 'storage_key', 'bill_number', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
            require(forbidden not in text, f'api leaks forbidden field: {forbidden}')
    page = client.get('/license-admin')
    require(page.status_code == 200, 'license admin page failed')
    for item in ['授权云服务后台', '客户管理', '产品管理', '授权管理', '授权审计']:
        require(item in page.text, f'page missing: {item}')
    for forbidden in ['tenant_id', 'project_id', 'storage_key', 'bill_number', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        require(forbidden not in page.text, f'page leaks forbidden field: {forbidden}')
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    require('scripts/saas_license_cloud_management_check.py' in gate, 'release gate missing license cloud management check')
    print('saas_license_cloud_management_check: PASS')


if __name__ == '__main__':
    main()
