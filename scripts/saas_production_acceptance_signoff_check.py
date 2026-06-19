#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production acceptance signoff page and export routes."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app
import server.saas_production_acceptance_pages as production_pages

SCRIPT = 'scripts/saas_production_acceptance_signoff_check.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    temp_dir = tempfile.TemporaryDirectory()
    production_pages.ROOT = Path(temp_dir.name)
    (production_pages.ROOT / 'release').mkdir(parents=True, exist_ok=True)
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '生产签收检查物业', 'project_name': '生产签收检查项目',
        'username': 'admin', 'role_code': 'system_admin',
    })
    require(login.status_code == 200, 'login failed')
    page = client.get('/backoffice/production-acceptance')
    for item in ['/backoffice/production-acceptance/signoff', '/backoffice/production-acceptance/signoff/print', '/backoffice/production-acceptance/signoff/download.md']:
        require(item in page.text, f'missing signoff link: {item}')
    print('PASS production acceptance signoff links')
    form = client.get('/backoffice/production-acceptance/signoff')
    require(form.status_code == 200 and '生产验收签收表' in form.text, 'signoff form missing')
    saved = client.post('/backoffice/production-acceptance/signoff', data={
        'operator_name': '实施检查', 'server_domain': 'saas.example.com', 'acceptance_status': 'PASS',
        'customer_signer': '客户检查', 'implementation_signer': '实施签字', 'signoff_date': '2026-06-19', 'notes': '检查通过',
    }, follow_redirects=False)
    require(saved.status_code == 303, 'signoff save failed')
    printable = client.get('/backoffice/production-acceptance/signoff/print')
    download = client.get('/backoffice/production-acceptance/signoff/download.md')
    require(printable.status_code == 200 and 'window.print' in printable.text, 'printable signoff missing')
    require(download.status_code == 200 and 'attachment;' in download.headers.get('content-disposition', ''), 'markdown download missing')
    for text in [form.text, printable.text, download.text]:
        for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id']:
            require(hidden not in text, f'forbidden signoff content: {hidden}')
    print('PASS production acceptance signoff form export')
    other = TestClient(create_app())
    other.post('/api/auth/login', json={
        'tenant_name': '生产签收检查物业', 'project_name': '生产签收检查项目',
        'username': 'reader', 'role_code': 'executive',
    })
    require(other.get('/backoffice/production-acceptance/signoff').status_code == 403, 'non-admin can edit signoff')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('PASS production acceptance signoff registry')
    temp_dir.cleanup()
    print('saas_production_acceptance_signoff_check: PASS')


if __name__ == '__main__':
    main()
