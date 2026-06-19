#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""License cloud management API and page for commercial admin."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_license_cloud import LicenseCloudService, create_license_app


def test_license_cloud_management_api_creates_lists_and_audits_without_business_fields():
    client = TestClient(create_license_app())

    customer = client.post('/api/license/customers', json={
        'customer_code': 'cust-gamma',
        'name': '丙方物业公司',
    })
    assert customer.status_code == 200
    assert customer.json()['item']['customer_code'] == 'cust-gamma'

    product = client.post('/api/license/products', json={
        'product_code': 'property-saas-backoffice',
        'name': '物业收费 SaaS 员工后台',
    })
    assert product.status_code == 200

    entitlement = client.post('/api/license/entitlements', json={
        'customer_code': 'cust-gamma',
        'product_code': 'property-saas-backoffice',
        'seats': 12,
        'expires_at': '2099-12-31',
    })
    assert entitlement.status_code == 200
    assert entitlement.json()['item']['status'] == 'active'

    customers = client.get('/api/license/customers')
    products = client.get('/api/license/products')
    entitlements = client.get('/api/license/entitlements')
    audits = client.get('/api/license/audit-logs')
    for response in [customers, products, entitlements, audits]:
        assert response.status_code == 200
        text = str(response.json())
        assert 'tenant_id' not in text
        assert 'project_id' not in text
        assert 'charge_target' not in text
        assert 'bill_number' not in text
        assert 'storage_key' not in text

    assert customers.json()['items'][0]['name'] == '丙方物业公司'
    assert products.json()['items'][0]['product_code'] == 'property-saas-backoffice'
    assert entitlements.json()['items'][0]['seats'] == 12
    actions = [item['action'] for item in audits.json()['items']]
    assert 'customer.create' in actions
    assert 'product.create' in actions
    assert 'entitlement.issue' in actions


def test_license_cloud_management_page_shows_admin_console_without_secret_or_business_fields():
    service = LicenseCloudService.in_memory()
    service.create_customer('cust-delta', '丁方物业公司')
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.issue_entitlement('cust-delta', 'property-saas-backoffice', seats=6, expires_at='2099-12-31')
    client = TestClient(create_license_app(service=service))

    page = client.get('/license-admin')

    assert page.status_code == 200
    for text in ['授权云服务后台', '客户管理', '产品管理', '授权管理', '授权审计', 'cust-delta', 'property-saas-backoffice']:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', 'storage_key', 'bill_number']:
        assert hidden not in page.text


def test_license_cloud_management_validation_blocks_invalid_seats_and_unknown_refs():
    client = TestClient(create_license_app())
    client.post('/api/license/customers', json={'customer_code': 'cust-epsilon', 'name': '戊方物业公司'})
    client.post('/api/license/products', json={'product_code': 'property-saas-backoffice', 'name': '物业收费 SaaS 员工后台'})

    invalid_seats = client.post('/api/license/entitlements', json={
        'customer_code': 'cust-epsilon',
        'product_code': 'property-saas-backoffice',
        'seats': 0,
        'expires_at': '2099-12-31',
    })
    assert invalid_seats.status_code == 400

    unknown = client.post('/api/license/entitlements', json={
        'customer_code': 'missing-customer',
        'product_code': 'property-saas-backoffice',
        'seats': 1,
        'expires_at': '2099-12-31',
    })
    assert unknown.status_code == 400


def test_license_cloud_management_assets_are_in_release_gate():
    script = Path('scripts/saas_license_cloud_management_check.py')
    assert script.exists(), 'missing license cloud management check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_cloud_management_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_cloud_management_check.py' in gate
