#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check sanitized production acceptance evidence package download."""

import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app
import server.saas_production_acceptance_pages as production_pages

SCRIPT = 'scripts/saas_production_acceptance_evidence_package_check.py'
EXPECTED = {
    'manifest.json', 'saas-production-acceptance-result.md', 'saas-release-evidence.md',
    'saas-isolation-evidence.md', 'production_acceptance_signoffs/history.json', 'backup-coverage.md',
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory() as td:
        production_pages.ROOT = Path(td)
        release = production_pages.ROOT / 'release'
        history = release / 'production_acceptance_signoffs'
        history.mkdir(parents=True)
        (release / 'saas-production-acceptance-result.md').write_text('验收留档\nPOSTGRES_PASSWORD=secret', encoding='utf-8')
        (release / 'saas-release-evidence.md').write_text('上线证据\nAPP_SECRET_KEY=secret\n.env.example', encoding='utf-8')
        (release / 'saas-isolation-evidence.md').write_text('隔离证据\ntenant_id=1', encoding='utf-8')
        (history / 'history.json').write_text('{"records":[{"notes":"历史签收"}]}', encoding='utf-8')
        client = TestClient(create_app())
        login = client.post('/api/auth/login', json={
            'tenant_name': '证据包检查物业', 'project_name': '证据包检查项目',
            'username': 'admin', 'role_code': 'system_admin',
        })
        require(login.status_code == 200, 'login failed')
        page = client.get('/backoffice/production-acceptance')
        require('/backoffice/production-acceptance/evidence-package.zip' in page.text, 'missing package link')
        response = client.get('/backoffice/production-acceptance/evidence-package.zip')
        require(response.status_code == 200, 'package download failed')
        require('attachment;' in response.headers.get('content-disposition', ''), 'package not attachment')
        with zipfile.ZipFile(io.BytesIO(response.content)) as package:
            names = set(package.namelist())
            require(EXPECTED.issubset(names), f'missing package files: {EXPECTED - names}')
            manifest = json.loads(package.read('manifest.json').decode('utf-8'))
            require(manifest.get('kind') == 'property-saas-production-acceptance-evidence', 'bad manifest kind')
            require(manifest.get('contains_customer_uploads') is False, 'manifest allows customer uploads')
            require(manifest.get('contains_secrets') is False, 'manifest allows secrets')
            for name in EXPECTED:
                text = package.read(name).decode('utf-8')
                for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id', '.env']:
                    require(hidden not in text, f'forbidden package content {hidden} in {name}')
        reader = TestClient(create_app())
        reader.post('/api/auth/login', json={
            'tenant_name': '证据包检查物业', 'project_name': '证据包检查项目',
            'username': 'reader', 'role_code': 'executive',
        })
        require(reader.get('/backoffice/production-acceptance/evidence-package.zip').status_code == 403, 'non-admin can download package')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('saas_production_acceptance_evidence_package_check: PASS')


if __name__ == '__main__':
    main()
