#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backoffice backup pages show first tenant acceptance record coverage."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def _client():
    client = TestClient(create_app())
    response = client.post('/api/auth/login', json={
        'tenant_name': '验收备份页面物业',
        'project_name': '验收备份页面项目',
        'username': 'system_admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200
    return client


def _assert_safe(html):
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo']:
        assert hidden not in html


def test_backup_page_explains_system_files_include_acceptance_records():
    client = _client()
    page = client.get('/backoffice/backups')
    assert page.status_code == 200
    for text in ['首租户验收记录', 'system-files', '系统侧签收证据', 'first_tenant_acceptance/records.json']:
        assert text in page.text
    _assert_safe(page.text)


def test_backup_and_restore_drill_detail_show_acceptance_record_scope():
    client = _client()
    created = client.post('/backoffice/backups/create', follow_redirects=False)
    assert created.status_code == 303
    page = client.get('/backoffice/backups')
    backup_id = page.text.split('/backoffice/backups/')[1].split('"')[0]
    drill = client.post('/backoffice/backups/restore-drills', data={'backup_id': backup_id, 'scope': 'system-files'}, follow_redirects=False)
    assert drill.status_code == 303

    detail = client.get(f'/backoffice/backups/{backup_id}')
    drill_list = client.get('/backoffice/backups')
    drill_href = drill_list.text.split('/backoffice/backups/restore-drills/')[1].split('"')[0]
    drill_page = client.get(f'/backoffice/backups/restore-drills/{drill_href}')
    for response in [detail, drill_page]:
        assert response.status_code == 200
        assert '首租户验收记录' in response.text
        assert 'first_tenant_acceptance/records.json' in response.text
        _assert_safe(response.text)


def test_acceptance_backup_page_check_script_is_in_release_assets():
    script = 'scripts/saas_first_tenant_acceptance_backup_page_check.py'
    result = subprocess.run([sys.executable, script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
    assert result.returncode == 0, result.stdout
    for path in [
        'scripts/saas_release_gate.py',
        'scripts/saas_release_evidence.py',
        'server/saas_deploy.py',
        'server/saas_commercial_readiness.py',
    ]:
        assert script in Path(path).read_text(encoding='utf-8')
