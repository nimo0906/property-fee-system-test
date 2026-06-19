#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant business config management page."""

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_tenant_business_config import business_template_for_user


def _login(client, role_code='system_admin', tenant_name='业务配置物业'):
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant_name,
        'project_name': f'{tenant_name}项目',
        'username': role_code,
        'role_code': role_code,
    })
    assert response.status_code == 200
    service = client.app.state.saas_service
    tenant = next(item for item in service.tenants.values() if item['name'] == tenant_name)
    project = next(item for item in service.projects.values() if item['tenant_id'] == tenant['id'])
    user = next(item for item in service.users.values() if item['tenant_id'] == tenant['id'] and item['role_code'] == role_code)
    return {**user, 'tenant_name': tenant_name, 'project_name': project['name'], 'project_id': project['id']}


def test_backoffice_links_business_config_for_tenant_admin():
    client = TestClient(create_app())
    _login(client, 'system_admin')
    home = client.get('/backoffice')
    assert home.status_code == 200
    assert '业务配置' in home.text
    assert '/backoffice/tenant-business-config' in home.text


def test_tenant_admin_can_update_own_business_template_and_import_uses_it():
    client = TestClient(create_app())
    user = _login(client, 'system_admin', '商办客户')
    page = client.get('/backoffice/tenant-business-config')
    assert page.status_code == 200
    for item in ['业务配置', '当前业务模板', '住宅物业', '商业/商铺', '园区/办公', '混合项目']:
        assert item in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text

    updated = client.post('/backoffice/tenant-business-config', data={'business_template': 'office'}, follow_redirects=True)
    assert updated.status_code == 200
    assert '业务配置已保存' in updated.text
    assert '园区/办公 · 当前选择' in updated.text
    assert business_template_for_user(client.app.state.saas_service, None, user)['code'] == 'office'

    import_page = client.get('/backoffice/imports/templates/charge-targets')
    assert import_page.status_code == 200
    assert '园区A,办公楼,501,办公,120' in import_page.text


def test_finance_can_view_but_cannot_update_business_config():
    client = TestClient(create_app())
    _login(client, 'finance', '财务只读客户')
    page = client.get('/backoffice/tenant-business-config')
    assert page.status_code == 200
    assert '当前角色只能查看业务配置' in page.text
    denied = client.post('/backoffice/tenant-business-config', data={'business_template': 'commercial'})
    assert denied.status_code == 403


def test_business_config_isolated_between_tenants():
    client_a = TestClient(create_app())
    _login(client_a, 'system_admin', 'A业务客户')
    assert client_a.post('/backoffice/tenant-business-config', data={'business_template': 'commercial'}, follow_redirects=False).status_code == 303

    client_b = TestClient(client_a.app)
    _login(client_b, 'system_admin', 'B业务客户')
    page_b = client_b.get('/backoffice/tenant-business-config')
    assert page_b.status_code == 200
    assert '住宅物业 · 当前选择' in page_b.text
    assert '商业/商铺 · 当前选择' not in page_b.text
