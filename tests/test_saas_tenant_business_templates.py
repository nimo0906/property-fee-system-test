#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant business templates for first tenant onboarding."""

from fastapi.testclient import TestClient

from server.saas_app import create_app


def _platform_client():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '模板平台',
        'project_name': '模板平台项目',
        'username': 'platform_admin',
        'role_code': 'platform_admin',
    })
    assert login.status_code == 200
    return client


def test_first_tenant_wizard_shows_business_template_selector_and_guidance():
    client = _platform_client()
    page = client.get('/backoffice/first-tenant-wizard')
    assert page.status_code == 200
    required = [
        '业务模板', '住宅物业', '商业/商铺', '园区/办公', '混合项目',
        '收费对象字段', '推荐收费项目', '账单周期', '导入样例',
        '住宅楼,1单元,101,居民,80',
        '商业区,一层,A-001,商户,56.5',
        '园区A,办公楼,501,办公,120',
        '混合区,商住楼,201,居民,90',
    ]
    for item in required:
        assert item in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_create_first_tenant_preserves_selected_business_template_in_result():
    client = _platform_client()
    response = client.post('/backoffice/first-tenant-wizard/create', data={
        'tenant_name': '模板客户',
        'project_name': '模板项目',
        'project_code': 'TPL-001',
        'admin_username': 'tpl_admin',
        'admin_password': 'TplStrong123',
        'license_customer_code': 'CUST-TPL-001',
        'business_template': 'commercial',
    }, follow_redirects=True)
    assert response.status_code == 200
    for item in ['已选择业务模板：商业/商铺', '商铺号', '商户名称', '物业费', '租金', '水电费', '月度']:
        assert item in response.text
    assert 'TplStrong123' not in response.text


def test_import_template_page_lists_business_templates_and_download_samples():
    client = _platform_client()
    page = client.get('/backoffice/imports/templates/charge-targets?business_template=office')
    assert page.status_code == 200
    for item in [
        '业务模板字段建议', '园区/办公', '办公楼', '楼层/分区', '工位/房号',
        '物业费', '能耗费', '停车费', '月度',
        '园区A,办公楼,501,办公,120',
        '/api/imports/templates/charge-targets.csv?business_template=office',
    ]:
        assert item in page.text
    csv = client.get('/api/imports/templates/charge-targets.csv?business_template=commercial')
    assert csv.status_code == 200
    assert '商业区,一层,A-001,商户,56.5' in csv.text
    assert 'tenant_id' not in csv.text
    assert 'project_id' not in csv.text


def test_business_template_check_script_passes_and_gate_includes_it():
    import subprocess
    import sys
    from pathlib import Path

    script = Path('scripts/saas_tenant_business_template_check.py')
    assert script.exists(), 'missing business template check script'
    result = subprocess.run(
        [sys.executable, str(script)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_tenant_business_template_check: PASS' in result.stdout
    assert 'scripts/saas_tenant_business_template_check.py' in Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
