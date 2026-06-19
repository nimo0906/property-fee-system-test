#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 commercial backup and restore drill alignment for SaaS."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def login_client(database_url, tenant_name='商业备份物业', project_name='商业备份项目', username='admin'):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant_name, 'project_name': project_name, 'username': username, 'role_code': 'system_admin'
    })
    assert response.status_code == 200
    return client


def test_backup_api_returns_commercial_fields_without_internal_ids_or_paths():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = login_client(db_url, username='tenant_admin')
        backup = client.post('/api/backups/create').json()['item']
        drill = client.post('/api/restore-drills', json={'backup_id': backup['backup_id'], 'scope': 'database'}).json()['item']

        backups = client.get('/api/backups').json()['items']
        drills = client.get('/api/restore-drills').json()['items']

        assert backups[0]['backup_id'] == backup['backup_id']
        assert backups[0]['created_by_username'] == 'tenant_admin'
        assert backups[0]['audit_action'] == 'backup.create'
        assert backups[0]['audit_log_id']
        assert drills[0]['backup_id'] == backup['backup_id']
        assert drills[0]['created_by_username'] == 'tenant_admin'
        assert drills[0]['audit_action'] == 'restore.drill'
        assert drills[0]['audit_log_id']
        forbidden_text = str({'backups': backups, 'drills': drills})
        for hidden in ['tenant_id', 'project_id', '/var/lib/property-saas', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
            assert hidden not in forbidden_text


def test_backup_and_restore_detail_pages_show_operator_and_audit_links_without_secrets():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = login_client(db_url, username='operator_admin')
        backup = client.post('/api/backups/create').json()['item']
        drill = client.post('/api/restore-drills', json={'backup_id': backup['backup_id'], 'scope': 'tenant-files'}).json()['item']

        backup_page = client.get(f"/backoffice/backups/{backup['backup_id']}")
        drill_page = client.get(f"/backoffice/backups/restore-drills/{drill['id']}")

        assert backup_page.status_code == 200
        assert drill_page.status_code == 200
        for text in ['操作人', 'operator_admin', '审计日志', '/backoffice/audit-logs/']:
            assert text in backup_page.text
            assert text in drill_page.text
        for hidden in ['tenant_id', 'project_id', '/var/lib/property-saas', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
            assert hidden not in backup_page.text
            assert hidden not in drill_page.text


def test_backup_api_is_tenant_scoped_for_restore_drills():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client_a = login_client(db_url, tenant_name='A商业备份物业', project_name='A项目', username='admin_a')
        backup_a = client_a.post('/api/backups/create').json()['item']
        client_a.post('/api/restore-drills', json={'backup_id': backup_a['backup_id'], 'scope': 'database'})

        client_b = login_client(db_url, tenant_name='B商业备份物业', project_name='B项目', username='admin_b')
        assert client_b.get('/api/backups').json()['items'] == []
        assert client_b.get('/api/restore-drills').json()['items'] == []
        assert client_b.post('/api/restore-drills', json={'backup_id': backup_a['backup_id'], 'scope': 'database'}).status_code == 403
