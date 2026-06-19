#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant delivery flow links recommended fee initialization."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def _client(role_code='platform_admin'):
    client = TestClient(create_app())
    response = client.post('/api/auth/login', json={
        'tenant_name': '交付收费初始化',
        'project_name': '交付收费初始化项目',
        'username': role_code,
        'role_code': role_code,
    })
    assert response.status_code == 200
    return client


def test_first_tenant_wizard_links_fee_template_initialization():
    client = _client('platform_admin')
    page = client.get('/backoffice/first-tenant-wizard')
    assert page.status_code == 200
    for item in [
        '一键初始化推荐收费项目',
        '/backoffice/fee-types/init-from-template',
        '按业务模板生成推荐收费项目',
        '配置收费项目',
    ]:
        assert item in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_delivery_package_includes_fee_template_initialization_entry():
    client = _client('system_admin')
    page = client.get('/backoffice/first-tenant-delivery-package')
    assert page.status_code == 200
    for item in [
        '推荐收费项目初始化',
        '/backoffice/fee-types/init-from-template',
        '按当前业务模板一键创建推荐收费项目',
    ]:
        assert item in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_delivery_checks_cover_fee_template_initialization():
    for script in [
        'scripts/saas_first_tenant_delivery_loop_check.py',
        'scripts/saas_first_tenant_delivery_package_check.py',
    ]:
        result = subprocess.run(
            [sys.executable, script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=60, check=False,
        )
        assert result.returncode == 0, result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_first_tenant_fee_init_delivery_check.py' in gate
