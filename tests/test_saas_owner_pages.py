#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS owner directory pages for module 4."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def login_client(database_url=None, role_code='finance'):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '业主目录物业',
        'project_name': '业主目录项目',
        'username': role_code,
        'role_code': role_code,
    })
    assert response.status_code == 200
    return client


def test_backoffice_owner_directory_lists_owners_and_bound_rooms_without_secret_fields():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = login_client(db_url)
        owner = client.post('/api/owners', json={'name': '张业主', 'phone': '13800000000', 'owner_type': '业主'}).json()['item']
        client.post('/api/charge-targets', json={
            'owner_id': owner['id'],
            'building': '1栋',
            'unit': '1单元',
            'room_number': '101',
            'category': '居民',
            'area': 88,
        })

        page = client.get('/backoffice/owners')

        assert page.status_code == 200
        for text in ['业主档案', '张业主', '13800000000', '业主', '绑定房间/铺位', '1栋-1单元-101', '新增业主']:
            assert text in page.text
        for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
            assert hidden not in page.text


def test_backoffice_owner_directory_is_discoverable_from_home_and_charge_target_page():
    client = login_client()

    home = client.get('/backoffice')
    targets = client.get('/backoffice/charge-targets')

    assert home.status_code == 200
    assert targets.status_code == 200
    assert '/backoffice/owners' in home.text
    assert '/backoffice/owners' in targets.text


def test_persistent_owner_and_charge_target_creates_are_audited():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = login_client(db_url)
        owner = client.post('/api/owners', json={'name': '审计业主', 'phone': '13900000000', 'owner_type': '住户'})
        assert owner.status_code == 200
        target = client.post('/api/charge-targets', json={
            'owner_id': owner.json()['item']['id'],
            'building': '2栋',
            'unit': '2单元',
            'room_number': '202',
            'category': '居民',
            'area': 92,
        })
        assert target.status_code == 200

        repo = create_saas_repository(db_url)
        tenant = repo.list_tenants()[0]
        project = repo.list_projects()[0]
        logs = repo.list_audit_logs(tenant['id'], project['id'])
        repo.close()

    actions = [row['action'] for row in logs]
    assert 'owner.create' in actions
    assert 'charge_target.create' in actions
    assert '13900000000' not in str(logs)
