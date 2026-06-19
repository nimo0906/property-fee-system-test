#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant delivery package overview page."""

from fastapi.testclient import TestClient

from server.saas_app import create_app


def _login(role='platform_admin'):
    client = TestClient(create_app())
    response = client.post('/api/auth/login', json={
        'tenant_name': '交付包物业',
        'project_name': '交付包项目',
        'username': role,
        'role_code': role,
    })
    assert response.status_code == 200
    return client


def test_delivery_package_page_collects_all_implementation_entries():
    client = _login('platform_admin')
    page = client.get('/backoffice/first-tenant-delivery-package')
    assert page.status_code == 200
    required = [
        '首租户交付包总览',
        '实施人员统一入口',
        '登录入口',
        '客户首租户初始化向导',
        '首租户业务引导闭环',
        '首租户交付验收记录',
        '验收记录打印版',
        'HTML 导出',
        '生产部署一键自检',
        '备份恢复演练',
        '授权绑定',
        '租户隔离证据',
        '客户上传数据与系统自身数据隔离',
        '/login',
        '/backoffice/first-tenant-wizard',
        '/backoffice/first-tenant-acceptance',
        '/backoffice/first-tenant-acceptance/print',
        '/backoffice/first-tenant-acceptance/export.html',
        '/backoffice/deploy-checklist',
        '/backoffice/backups',
        '/backoffice/license-ops',
        '/backoffice/data-boundaries',
    ]
    for item in required:
        assert item in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_delivery_package_requires_admin_and_home_links_it_for_platform_admin():
    executive = _login('executive')
    assert executive.get('/backoffice/first-tenant-delivery-package').status_code == 403

    platform = _login('platform_admin')
    home = platform.get('/backoffice')
    assert home.status_code == 200
    assert '首租户交付包' in home.text
    assert '/backoffice/first-tenant-delivery-package' in home.text


def test_delivery_package_check_script_passes_and_gate_includes_it():
    import subprocess
    import sys
    from pathlib import Path

    script = Path('scripts/saas_first_tenant_delivery_package_check.py')
    assert script.exists(), 'missing delivery package check script'
    result = subprocess.run(
        [sys.executable, str(script)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_first_tenant_delivery_package_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_first_tenant_delivery_package_check.py' in gate
