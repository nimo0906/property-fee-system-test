#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Visual login and first tenant delivery wizard pages."""

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_visual_login_page_posts_to_form_login_and_hides_internal_fields():
    client = TestClient(create_app())
    page = client.get('/login')
    assert page.status_code == 200
    for text in [
        '物业收费管理系统 SaaS',
        '商业版员工后台登录',
        '客户公司',
        '项目名称',
        '登录账号',
        '角色',
        '进入员工后台',
        '客户数据隔离',
        '系统自身数据隔离',
        '正式商业云端后台',
    ]:
        assert text in page.text
    assert 'action="/login"' in page.text
    assert 'method="post"' in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_login_form_sets_session_and_redirects_to_backoffice():
    client = TestClient(create_app())
    response = client.post('/login', data={
        'tenant_name': '界面演示物业',
        'project_name': '界面演示项目',
        'username': 'tenant_admin',
        'role_code': 'system_admin',
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/backoffice'
    assert 'session_id' in response.headers.get('set-cookie', '')
    home = client.get('/backoffice')
    assert home.status_code == 200
    assert '界面演示物业' in home.text
    assert '界面演示项目' in home.text


def test_first_tenant_wizard_page_shows_delivery_steps_for_platform_admin_only():
    client = TestClient(create_app())
    tenant_login = client.post('/api/auth/login', json={
        'tenant_name': '普通客户',
        'project_name': '普通项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert tenant_login.status_code == 200
    assert client.get('/backoffice/first-tenant-wizard').status_code == 403

    platform = TestClient(create_app())
    login = platform.post('/api/auth/login', json={
        'tenant_name': '平台运营',
        'project_name': '平台项目',
        'username': 'platform_admin',
        'role_code': 'platform_admin',
    })
    assert login.status_code == 200
    page = platform.get('/backoffice/first-tenant-wizard')
    assert page.status_code == 200
    for text in [
        '客户首租户初始化向导',
        '创建客户公司',
        '创建默认项目',
        '创建租户管理员',
        '绑定授权客户编号',
        '导入收费对象模板',
        '配置收费项目',
        '生成首批测试账单',
        '登记测试收款',
        '验收租户隔离',
        '执行备份恢复演练',
        '客户上传数据与系统自身数据隔离',
        '业务数据不进入授权云服务',
    ]:
        assert text in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_first_tenant_wizard_create_redirects_to_next_delivery_steps():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '平台运营',
        'project_name': '平台项目',
        'username': 'platform_admin',
        'role_code': 'platform_admin',
    })
    assert login.status_code == 200
    response = client.post('/backoffice/first-tenant-wizard/create', data={
        'tenant_name': '首租户物业',
        'project_name': '首租户项目',
        'project_code': 'FIRST-001',
        'admin_username': 'first_admin',
        'admin_password': 'StrongPass123',
        'license_customer_code': 'CUST-FIRST-001',
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'].startswith('/backoffice/first-tenant-wizard?message=')
    page = client.get(response.headers['location'])
    assert page.status_code == 200
    for text in ['首租户物业', '首租户项目', 'CUST-FIRST-001', '下一步：导入收费对象模板', '下一步：配置收费项目']:
        assert text in page.text
    for hidden in ['StrongPass123', 'tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text
