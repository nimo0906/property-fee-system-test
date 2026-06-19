#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production acceptance signoff history."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app
import server.saas_production_acceptance_pages as production_pages

SCRIPT = 'scripts/saas_production_acceptance_signoff_history_check.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def _post(client, operator, note):
    return client.post('/backoffice/production-acceptance/signoff', data={
        'operator_name': operator, 'server_domain': 'saas-history.example.com', 'acceptance_status': 'PASS',
        'customer_signer': f'{operator}客户', 'implementation_signer': f'{operator}签字', 'signoff_date': '2026-06-19', 'notes': note,
    }, follow_redirects=False)


def main():
    temp_dir = tempfile.TemporaryDirectory()
    production_pages.ROOT = Path(temp_dir.name)
    (production_pages.ROOT / 'release').mkdir(parents=True, exist_ok=True)
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '签收历史检查物业', 'project_name': '签收历史检查项目',
        'username': 'admin', 'role_code': 'system_admin',
    })
    require(login.status_code == 200, 'login failed')
    require(_post(client, '实施A', '第一次').status_code == 303, 'first save failed')
    require(_post(client, '实施B', '第二次').status_code == 303, 'second save failed')
    page = client.get('/backoffice/production-acceptance/signoff')
    require('签收历史记录' in page.text and '第一次' in page.text and '第二次' in page.text, 'history page missing records')
    download = client.get('/backoffice/production-acceptance/signoff/history/1/download.md')
    require(download.status_code == 200 and '第一次' in download.text and '第二次' not in download.text, 'history download wrong')
    for text in [page.text, download.text]:
        for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id']:
            require(hidden not in text, f'forbidden history content: {hidden}')
    print('PASS production acceptance signoff history records')
    reader = TestClient(create_app())
    reader.post('/api/auth/login', json={
        'tenant_name': '签收历史检查物业', 'project_name': '签收历史检查项目',
        'username': 'reader', 'role_code': 'executive',
    })
    require(reader.get('/backoffice/production-acceptance/signoff/history/1/download.md').status_code == 403, 'non-admin can download history')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('PASS production acceptance signoff history registry')
    temp_dir.cleanup()
    print('saas_production_acceptance_signoff_history_check: PASS')


if __name__ == '__main__':
    main()
