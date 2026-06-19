#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preview and download links for production acceptance evidence files."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_acceptance_evidence_download_check.py'
SCRIPT_REF = 'scripts/saas_production_acceptance_evidence_download_check.py'


def _login(client):
    return client.post('/api/auth/login', json={
        'tenant_name': '证据下载物业',
        'project_name': '证据下载项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })


def test_production_acceptance_page_has_preview_and_download_links():
    client = TestClient(create_app())
    assert _login(client).status_code == 200
    page = client.get('/backoffice/production-acceptance')
    assert page.status_code == 200
    for key in ['acceptance-result', 'release-evidence', 'isolation-evidence']:
        assert f'/backoffice/production-acceptance/evidence/{key}' in page.text
        assert f'/backoffice/production-acceptance/evidence/{key}/download' in page.text
    for label in ['预览', '下载']:
        assert label in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo']:
        assert hidden not in page.text


def test_evidence_preview_and_download_routes_are_login_scoped_and_sanitized():
    anonymous = TestClient(create_app())
    assert anonymous.get('/backoffice/production-acceptance/evidence/acceptance-result').status_code in {401, 403}

    client = TestClient(create_app())
    assert _login(client).status_code == 200
    preview = client.get('/backoffice/production-acceptance/evidence/acceptance-result')
    assert preview.status_code == 200
    assert 'SaaS 生产上线验收结果留档' in preview.text
    assert '<pre' in preview.text
    download = client.get('/backoffice/production-acceptance/evidence/acceptance-result/download')
    assert download.status_code == 200
    assert 'text/markdown' in download.headers.get('content-type', '')
    assert 'attachment;' in download.headers.get('content-disposition', '')
    assert 'saas-production-acceptance-result.md' in download.headers.get('content-disposition', '')
    assert 'SaaS 生产上线验收结果留档' in download.text
    bad = client.get('/backoffice/production-acceptance/evidence/../../server.py')
    assert bad.status_code in {400, 404}
    for body in [preview.text, download.text]:
        for hidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo', 'tenant_id', 'project_id']:
            assert hidden not in body


def test_evidence_download_check_is_registered_and_passes():
    assert SCRIPT.exists(), 'missing evidence download check script'
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for item in [
        'PASS production acceptance evidence links',
        'PASS production acceptance evidence preview download',
        'PASS production acceptance evidence download registry',
        'saas_production_acceptance_evidence_download_check: PASS',
    ]:
        assert item in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
