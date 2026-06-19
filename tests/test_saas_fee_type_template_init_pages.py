#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee type recommendation initialization from tenant business template."""

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_tenant_business_config import save_tenant_business_template


def _login(client, role_code='system_admin', tenant_name='推荐收费客户'):
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


def test_fee_type_page_shows_template_recommendations_without_internal_fields():
    client = TestClient(create_app())
    user = _login(client, 'system_admin', '商业收费客户')
    save_tenant_business_template(client.app.state.saas_service, None, user, 'commercial')

    page = client.get('/backoffice/fee-types')
    assert page.status_code == 200
    for item in ['模板推荐收费项目', '商业/商铺', '物业费', '租金', '水电费', '一键初始化推荐收费项目']:
        assert item in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_tenant_admin_can_initialize_recommended_fee_types_idempotently():
    client = TestClient(create_app())
    user = _login(client, 'system_admin', '园区收费客户')
    service = client.app.state.saas_service
    save_tenant_business_template(service, None, user, 'office')

    first = client.post('/backoffice/fee-types/init-from-template', follow_redirects=True)
    assert first.status_code == 200
    assert '已初始化推荐收费项目 3 项' in first.text
    names = [item['name'] for item in service.list_fee_types(user, user['project_id'])]
    assert names == ['物业费', '能耗费', '停车费']

    second = client.post('/backoffice/fee-types/init-from-template', follow_redirects=True)
    assert second.status_code == 200
    assert '推荐收费项目已存在，未重复创建' in second.text
    names_after = [item['name'] for item in service.list_fee_types(user, user['project_id'])]
    assert names_after == names


def test_finance_cannot_initialize_recommended_fee_types():
    client = TestClient(create_app())
    _login(client, 'finance', '财务推荐客户')
    denied = client.post('/backoffice/fee-types/init-from-template')
    assert denied.status_code == 403


def test_template_fee_initialization_is_tenant_project_scoped():
    app = create_app()
    client_a = TestClient(app)
    user_a = _login(client_a, 'system_admin', 'A推荐客户')
    save_tenant_business_template(app.state.saas_service, None, user_a, 'commercial')
    assert client_a.post('/backoffice/fee-types/init-from-template', follow_redirects=False).status_code == 303

    client_b = TestClient(app)
    user_b = _login(client_b, 'system_admin', 'B推荐客户')
    items_b = app.state.saas_service.list_fee_types(user_b, user_b['project_id'])
    assert items_b == []
