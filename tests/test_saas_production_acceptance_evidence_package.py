#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production acceptance evidence package download."""

import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_acceptance_evidence_package_check.py'
SCRIPT_REF = 'scripts/saas_production_acceptance_evidence_package_check.py'


def _login(client, role='system_admin'):
    response = client.post('/api/auth/login', json={
        'tenant_name': '证据总包物业',
        'project_name': '证据总包项目',
        'username': 'admin',
        'role_code': role,
    })
    assert response.status_code == 200


def _assert_safe(text):
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo', '.env']:
        assert hidden not in text


def test_production_acceptance_page_links_evidence_package_download():
    client = TestClient(create_app())
    _login(client)
    page = client.get('/backoffice/production-acceptance')
    assert page.status_code == 200
    assert '下载交付证据包' in page.text
    assert '/backoffice/production-acceptance/evidence-package.zip' in page.text
    _assert_safe(page.text)


def test_evidence_package_zip_contains_sanitized_delivery_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr('server.saas_production_acceptance_pages.ROOT', tmp_path)
    release = tmp_path / 'release'
    history_dir = release / 'production_acceptance_signoffs'
    history_dir.mkdir(parents=True)
    (release / 'saas-production-acceptance-result.md').write_text('验收留档\nPOSTGRES_PASSWORD=secret\ntenant_id=1\n/Users/nimo/private', encoding='utf-8')
    (release / 'saas-release-evidence.md').write_text('上线证据\nAPP_SECRET_KEY=secret\nproject_id=2\n.env.example', encoding='utf-8')
    (release / 'saas-isolation-evidence.md').write_text('隔离证据\n客户上传数据与系统自身数据隔离', encoding='utf-8')
    (history_dir / 'history.json').write_text('{"records":[{"notes":"历史签收","markdown":"签收正文 tenant_id"}]}', encoding='utf-8')

    client = TestClient(create_app())
    _login(client)
    response = client.get('/backoffice/production-acceptance/evidence-package.zip')
    assert response.status_code == 200
    assert 'application/zip' in response.headers.get('content-type', '')
    assert 'attachment;' in response.headers.get('content-disposition', '')
    assert 'saas-production-acceptance-evidence.zip' in response.headers.get('content-disposition', '')

    with zipfile.ZipFile(io.BytesIO(response.content)) as package:
        names = set(package.namelist())
        expected = {
            'manifest.json',
            'saas-production-acceptance-result.md',
            'saas-release-evidence.md',
            'saas-isolation-evidence.md',
            'production_acceptance_signoffs/history.json',
            'backup-coverage.md',
        }
        assert expected.issubset(names)
        assert not any(name.endswith('.env') or 'customer_files' in name for name in names)
        manifest = json.loads(package.read('manifest.json').decode('utf-8'))
        assert manifest['kind'] == 'property-saas-production-acceptance-evidence'
        assert manifest['contains_customer_uploads'] is False
        assert manifest['contains_secrets'] is False
        assert 'backup-coverage.md' in manifest['files']
        for name in expected:
            text = package.read(name).decode('utf-8')
            _assert_safe(text)
        assert '验收留档' in package.read('saas-production-acceptance-result.md').decode('utf-8')
        assert '历史签收' in package.read('production_acceptance_signoffs/history.json').decode('utf-8')
        assert 'system-files' in package.read('backup-coverage.md').decode('utf-8')


def test_evidence_package_is_admin_scoped_and_registered():
    non_admin = TestClient(create_app())
    _login(non_admin, role='executive')
    assert non_admin.get('/backoffice/production-acceptance/evidence-package.zip').status_code == 403

    assert SCRIPT.exists(), 'missing evidence package check script'
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
    assert 'saas_production_acceptance_evidence_package_check: PASS' in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
