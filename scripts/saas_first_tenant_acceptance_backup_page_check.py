#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check backup pages explain first tenant acceptance record coverage."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app

FORBIDDEN = ["tenant_id", "project_id", "POSTGRES_PASSWORD", "APP_SECRET_KEY", "/Users/nimo"]
REQUIRED = ["首租户验收记录", "system-files", "系统侧签收证据", "first_tenant_acceptance/records.json"]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def assert_page(html):
    for item in REQUIRED:
        require(item in html, f'missing backup page text: {item}')
    for item in FORBIDDEN:
        require(item not in html, f'forbidden page content: {item}')


def main():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '验收备份页面检查',
        'project_name': '验收备份页面项目',
        'username': 'system_admin',
        'role_code': 'system_admin',
    })
    require(login.status_code == 200, 'login failed')
    page = client.get('/backoffice/backups')
    require(page.status_code == 200, 'backup page failed')
    assert_page(page.text)
    created = client.post('/backoffice/backups/create', follow_redirects=False)
    require(created.status_code == 303, 'create backup failed')
    page = client.get('/backoffice/backups')
    backup_id = page.text.split('/backoffice/backups/')[1].split('"')[0]
    drill = client.post('/backoffice/backups/restore-drills', data={'backup_id': backup_id, 'scope': 'system-files'}, follow_redirects=False)
    require(drill.status_code == 303, 'restore drill failed')
    detail = client.get(f'/backoffice/backups/{backup_id}')
    drill_list = client.get('/backoffice/backups')
    drill_href = drill_list.text.split('/backoffice/backups/restore-drills/')[1].split('"')[0]
    drill_page = client.get(f'/backoffice/backups/restore-drills/{drill_href}')
    for response in [detail, drill_page]:
        require(response.status_code == 200, 'detail page failed')
        assert_page(response.text)
    print('saas_first_tenant_acceptance_backup_page_check: PASS')


if __name__ == '__main__':
    main()
