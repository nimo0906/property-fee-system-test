#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent license cloud service boundary for SaaS commercial edition."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_license_cloud import (
    LicenseCloudService,
    build_license_service_boundary,
    build_license_service_schema,
    create_license_app,
)


def test_license_cloud_schema_is_independent_from_saas_business_tables():
    schema = build_license_service_schema()
    for required in [
        'license_customers',
        'license_products',
        'license_entitlements',
        'license_audit_logs',
        'customer_code',
        'product_code',
    ]:
        assert required in schema
    for forbidden in [
        'CREATE TABLE IF NOT EXISTS tenants',
        'CREATE TABLE IF NOT EXISTS projects',
        'CREATE TABLE IF NOT EXISTS owners',
        'CREATE TABLE IF NOT EXISTS charge_targets',
        'CREATE TABLE IF NOT EXISTS fee_types',
        'CREATE TABLE IF NOT EXISTS bills',
        'CREATE TABLE IF NOT EXISTS payments',
        'CREATE TABLE IF NOT EXISTS imports',
        'tenant_id',
        'project_id',
    ]:
        assert forbidden not in schema


def test_license_cloud_service_checks_entitlement_without_business_data():
    service = LicenseCloudService.in_memory()
    customer = service.create_customer('cust-alpha', '甲方物业公司')
    product = service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    entitlement = service.issue_entitlement(customer['customer_code'], product['product_code'], seats=20, expires_at='2099-12-31')

    result = service.check_license('cust-alpha', 'property-saas-backoffice')

    assert result['status'] == 'active'
    assert result['allowed'] is True
    assert result['seats'] == 20
    assert result['expires_at'] == '2099-12-31'
    assert 'tenant_id' not in result
    assert 'project_id' not in result
    assert 'business_database_url' not in result
    assert entitlement['entitlement_code'].startswith('lic-')
    assert service.audit_logs[-1]['action'] == 'license.check'


def test_license_cloud_app_exposes_only_license_boundary():
    service = LicenseCloudService.in_memory()
    service.create_customer('cust-beta', '乙方物业公司')
    service.create_product('property-saas-backoffice', '物业收费 SaaS 员工后台')
    service.issue_entitlement('cust-beta', 'property-saas-backoffice', seats=8, expires_at='2099-12-31')
    client = TestClient(create_license_app(service=service))

    health = client.get('/health')
    assert health.status_code == 200
    assert health.json() == {'ok': True, 'service': 'property-license-cloud', 'storage': 'independent'}

    check = client.post('/api/license/check', json={
        'customer_code': 'cust-beta',
        'product_code': 'property-saas-backoffice',
    })
    assert check.status_code == 200
    assert check.json()['allowed'] is True

    boundary = client.get('/api/license/boundary')
    assert boundary.status_code == 200
    text = str(boundary.json())
    assert 'property_license_cloud' in text
    assert 'property_saas' not in text
    assert 'tenant_id' not in text
    assert 'project_id' not in text


def test_license_cloud_boundary_assets_and_release_gate():
    doc = Path('docs/saas-license-cloud-service-boundary.md')
    script = Path('scripts/saas_license_cloud_boundary_check.py')
    assert doc.exists(), 'missing license cloud boundary doc'
    assert script.exists(), 'missing license cloud boundary check script'
    text = doc.read_text(encoding='utf-8')
    for required in [
        '授权云服务后台边界设计',
        '独立服务',
        '独立数据库',
        '不得与 SaaS 业务主库混用',
        '不得保存客户上传业务数据',
        '只返回授权结果',
        'license_customers',
        'license_products',
        'license_entitlements',
        'license_audit_logs',
    ]:
        assert required in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text

    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_cloud_boundary_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_cloud_boundary_check.py' in gate
