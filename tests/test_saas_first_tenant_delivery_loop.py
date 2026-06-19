#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant post-onboarding delivery loop."""

from fastapi.testclient import TestClient

from server.saas_app import create_app


def _platform_client():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '平台运营',
        'project_name': '平台项目',
        'username': 'platform_admin',
        'role_code': 'platform_admin',
    })
    assert login.status_code == 200
    return client


def test_first_tenant_wizard_shows_business_delivery_loop_links_after_create():
    client = _platform_client()
    response = client.post('/backoffice/first-tenant-wizard/create', data={
        'tenant_name': '闭环物业',
        'project_name': '闭环一期',
        'project_code': 'LOOP-001',
        'admin_username': 'loop_admin',
        'admin_password': 'StrongLoop123',
        'license_customer_code': 'CUST-LOOP-001',
    }, follow_redirects=True)
    assert response.status_code == 200
    required = [
        '首租户业务引导闭环',
        '1. 导入收费对象模板',
        '2. 配置收费项目',
        '3. 生成首批测试账单',
        '4. 登记测试收款',
        '5. 查看欠费/实收报表',
        '6. 生成交付验收记录',
        '/backoffice/imports/templates/charge-targets',
        '/backoffice/imports',
        '/backoffice/fee-types',
        '/backoffice/bills',
        '/backoffice/payments',
        '/backoffice/reports',
        '/backoffice/acceptance',
        '租户隔离验收',
        '备份恢复演练',
        '客户上传数据与系统自身数据隔离',
    ]
    for item in required:
        assert item in response.text
    for hidden in ['StrongLoop123', 'tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in response.text


def test_first_tenant_wizard_empty_page_explains_delivery_loop_before_create():
    client = _platform_client()
    page = client.get('/backoffice/first-tenant-wizard')
    assert page.status_code == 200
    for item in [
        '首租户业务引导闭环',
        '创建完成后会显示可点击的业务交付路径',
        '导入收费对象模板',
        '配置收费项目',
        '生成首批测试账单',
        '登记测试收款',
        '查看欠费/实收报表',
        '生成交付验收记录',
    ]:
        assert item in page.text


def test_first_tenant_delivery_loop_check_script_passes_and_gate_includes_it():
    import subprocess
    import sys
    from pathlib import Path

    script = Path('scripts/saas_first_tenant_delivery_loop_check.py')
    assert script.exists(), 'missing delivery loop check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_first_tenant_delivery_loop_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_first_tenant_delivery_loop_check.py' in gate
