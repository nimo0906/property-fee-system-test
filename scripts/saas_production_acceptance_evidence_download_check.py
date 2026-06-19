#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production acceptance evidence preview/download links."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app

SCRIPT = 'scripts/saas_production_acceptance_evidence_download_check.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '证据下载检查物业', 'project_name': '证据下载检查项目',
        'username': 'admin', 'role_code': 'system_admin',
    })
    require(login.status_code == 200, 'login failed')
    page = client.get('/backoffice/production-acceptance')
    for key in ['acceptance-result', 'release-evidence', 'isolation-evidence']:
        require(f'/backoffice/production-acceptance/evidence/{key}' in page.text, f'missing preview link {key}')
        require(f'/backoffice/production-acceptance/evidence/{key}/download' in page.text, f'missing download link {key}')
    print('PASS production acceptance evidence links')
    preview = client.get('/backoffice/production-acceptance/evidence/acceptance-result')
    download = client.get('/backoffice/production-acceptance/evidence/acceptance-result/download')
    require(preview.status_code == 200 and '<pre' in preview.text, 'preview failed')
    require(download.status_code == 200 and 'attachment;' in download.headers.get('content-disposition', ''), 'download failed')
    for text in [preview.text, download.text]:
        for hidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo', 'tenant_id', 'project_id']:
            require(hidden not in text, f'forbidden evidence content: {hidden}')
    require(client.get('/backoffice/production-acceptance/evidence/../../server.py').status_code in {400, 404}, 'path traversal allowed')
    print('PASS production acceptance evidence preview download')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('PASS production acceptance evidence download registry')
    print('saas_production_acceptance_evidence_download_check: PASS')


if __name__ == '__main__':
    main()
