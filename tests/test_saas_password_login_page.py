#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formal password login page for persistent SaaS mode."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def _seed_repo(db_url):
    repo = create_saas_repository(db_url)
    platform = {'tenant_id': 0, 'project_id': 0, 'role_code': 'platform_admin', 'username': 'platform'}
    repo.onboard_tenant_for_platform(platform, '正式客户物业', '正式项目', 'tenant_admin', 'SecurePass123', 'PROD-001')


def test_login_page_in_persistent_mode_requires_password_field_without_secret_leaks():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        _seed_repo(db_url)
        client = TestClient(create_app(db_url))
        page = client.get('/login')
        assert page.status_code == 200
        for text in ['商业版员工后台登录', '登录密码', '正式账号密码登录', '密码不会写入页面、日志或审计明细']:
            assert text in page.text
        assert 'name="password"' in page.text
        for hidden in ['password_hash', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
            assert hidden not in page.text


def test_login_form_rejects_missing_or_wrong_password_in_persistent_mode():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        _seed_repo(db_url)
        client = TestClient(create_app(db_url))
        base = {
            'tenant_name': '正式客户物业',
            'project_name': '正式项目',
            'username': 'tenant_admin',
            'role_code': 'system_admin',
        }
        missing = client.post('/login', data=base, follow_redirects=False)
        assert missing.status_code == 303
        assert missing.headers['location'].startswith('/login?message=')
        assert 'session_id' not in missing.headers.get('set-cookie', '')
        wrong = client.post('/login', data={**base, 'password': 'WrongPass123'}, follow_redirects=False)
        assert wrong.status_code == 303
        assert wrong.headers['location'].startswith('/login?message=')
        assert 'session_id' not in wrong.headers.get('set-cookie', '')


def test_login_form_accepts_correct_password_in_persistent_mode_and_hides_password():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        _seed_repo(db_url)
        client = TestClient(create_app(db_url))
        response = client.post('/login', data={
            'tenant_name': '正式客户物业',
            'project_name': '正式项目',
            'username': 'tenant_admin',
            'role_code': 'system_admin',
            'password': 'SecurePass123',
        }, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'] in {'/backoffice', '/backoffice/change-password'}
        assert 'session_id' in response.headers.get('set-cookie', '')
        home = client.get('/backoffice', follow_redirects=False)
        assert home.status_code in {200, 303}
        assert 'SecurePass123' not in response.text
