#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 10 cloud UI replica gate tests."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]


def _login(client, role_code='finance', tenant='模块十物业', project='模块十项目'):
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': f'{role_code}_user',
        'role_code': role_code,
    })
    assert response.status_code == 200


def test_module10_gate_script_exists_and_is_registered():
    script = ROOT / 'scripts/saas_module10_cloud_ui_replica_gate.py'
    assert script.exists(), 'missing module 10 cloud UI replica gate script'
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_module10_cloud_ui_replica_gate.py' in gate


def test_module10_gate_documents_local_core_ui_replica_scope():
    text = (ROOT / 'scripts/saas_module10_cloud_ui_replica_gate.py').read_text(encoding='utf-8')
    for keyword in [
        'local core page shell',
        'sidebar navigation',
        'topbar account actions',
        'mobile menu',
        'core business pages',
        'tenant isolation',
        'release gate registration',
    ]:
        assert keyword in text


def test_cloud_core_pages_share_local_like_shell_navigation_and_no_secret_leakage():
    with tempfile.TemporaryDirectory() as td:
        client = TestClient(create_app(database_url=f"sqlite:///{Path(td) / 'saas.sqlite3'}"))
        _login(client)
        pages = [
            '/backoffice',
            '/backoffice/charge-targets',
            '/backoffice/fee-types',
            '/backoffice/bills',
            '/backoffice/payments',
            '/backoffice/reports',
            '/backoffice/imports',
        ]
        for path in pages:
            page = client.get(path)
            assert page.status_code == 200, path
            for text in [
                'app-shell',
                'sidebar',
                'sidebar-brand',
                'sidebar-nav',
                'mobile-menu-btn',
                'topbar',
                'page-title',
                'content-stack',
                '物业收费系统',
                '当前租户',
                '模块十物业',
                '模块十项目',
                '工作台',
                '收费对象',
                '收费项目',
                '出账审核',
                '收款登记',
                '欠费报表',
            ]:
                assert text in page.text, f'{text} missing in {path}'
            for hidden in ['APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env', 'idempotency_key']:
                assert hidden not in page.text


def test_cloud_ui_shell_keeps_role_based_admin_entries():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        finance = TestClient(create_app(database_url=db_url))
        _login(finance, role_code='finance')
        finance_page = finance.get('/backoffice')
        assert finance_page.status_code == 200
        assert '账号管理' not in finance_page.text
        assert '客户开通' not in finance_page.text

        admin = TestClient(create_app(database_url=db_url))
        _login(admin, role_code='system_admin')
        admin_page = admin.get('/backoffice')
        assert admin_page.status_code == 200
        for text in ['账号管理', '权限矩阵', '审计日志', '备份恢复', '云端上线']:
            assert text in admin_page.text
        assert '客户开通' not in admin_page.text
