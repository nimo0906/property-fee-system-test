#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant business config persistence and isolation."""

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_tenant_business_config import business_template_for_user


def _login(client, tenant_name, role_code='system_admin'):
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant_name,
        'project_name': f'{tenant_name}项目',
        'username': f'{tenant_name}_{role_code}',
        'role_code': role_code,
    })
    assert response.status_code == 200
    service = client.app.state.saas_service
    tenant = next(item for item in service.tenants.values() if item['name'] == tenant_name)
    project = next(item for item in service.projects.values() if item['tenant_id'] == tenant['id'])
    user = next(item for item in service.users.values() if item['tenant_id'] == tenant['id'] and item['role_code'] == role_code)
    return {**user, 'tenant_name': tenant_name, 'project_name': project['name'], 'project_id': project['id']}


def test_first_tenant_wizard_saves_business_template_to_tenant_config():
    client = TestClient(create_app())
    platform = _login(client, '平台配置', 'platform_admin')
    response = client.post('/backoffice/first-tenant-wizard/create', data={
        'tenant_name': '商业模板客户',
        'project_name': '商业模板项目',
        'project_code': 'COMM-001',
        'admin_username': 'comm_admin',
        'admin_password': 'CommStrong123',
        'license_customer_code': 'CUST-COMM-001',
        'business_template': 'commercial',
    }, follow_redirects=False)
    assert response.status_code == 303

    tenant_user = _login(client, '商业模板客户', 'system_admin')
    assert business_template_for_user(client.app.state.saas_service, None, tenant_user)['code'] == 'commercial'
    assert business_template_for_user(client.app.state.saas_service, None, platform)['code'] == 'residential'


def test_import_pages_use_current_tenant_business_template_without_internal_fields():
    client = TestClient(create_app())
    user_a = _login(client, '租户A', 'system_admin')
    service = client.app.state.saas_service
    service.tenant_business_configs = {int(user_a['tenant_id']): {'template_code': 'office'}}

    page = client.get('/backoffice/imports/templates/charge-targets')
    assert page.status_code == 200
    assert '园区/办公 · 当前选择' in page.text
    assert '园区A,办公楼,501,办公,120' in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text

    csv = client.get('/api/imports/templates/charge-targets.csv?current_tenant=1')
    assert csv.status_code == 200
    assert '园区A,办公楼,501,办公,120' in csv.text
    assert 'tenant_id' not in csv.text
    assert 'project_id' not in csv.text

    other = TestClient(client.app)
    _login(other, '租户B', 'system_admin')
    other_page = other.get('/backoffice/imports/templates/charge-targets')
    assert other_page.status_code == 200
    assert '住宅物业 · 当前选择' in other_page.text
    assert '园区/办公 · 当前选择' not in other_page.text
