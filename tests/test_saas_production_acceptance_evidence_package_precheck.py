#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production acceptance evidence package precheck status."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_production_acceptance_package import package_precheck

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_acceptance_evidence_package_precheck.py'
SCRIPT_REF = 'scripts/saas_production_acceptance_evidence_package_precheck.py'


def _login(client):
    response = client.post('/api/auth/login', json={
        'tenant_name': '证据包预检物业',
        'project_name': '证据包预检项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200


def _assert_safe(text):
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo', '.env']:
        assert hidden not in text


def test_package_precheck_reports_existing_and_missing_artifacts(tmp_path):
    release = tmp_path / 'release'
    release.mkdir()
    (release / 'saas-production-acceptance-result.md').write_text('ok', encoding='utf-8')
    (release / 'saas-isolation-evidence.md').write_text('ok', encoding='utf-8')
    rows = package_precheck(tmp_path)
    by_name = {row['package_name']: row for row in rows}
    assert by_name['saas-production-acceptance-result.md']['status'] == '存在'
    assert by_name['saas-production-acceptance-result.md']['included'] == '是'
    assert by_name['saas-release-evidence.md']['status'] == '缺失'
    assert by_name['saas-release-evidence.md']['included'] == '占位进入总包'
    assert by_name['production_acceptance_signoffs/history.json']['status'] == '缺失'
    assert by_name['backup-coverage.md']['status'] == '自动生成'
    assert by_name['backup-coverage.md']['included'] == '是'


def test_production_acceptance_page_shows_package_precheck_status(tmp_path, monkeypatch):
    monkeypatch.setattr('server.saas_production_acceptance_pages.ROOT', tmp_path)
    release = tmp_path / 'release'
    release.mkdir()
    (release / 'saas-production-acceptance-result.md').write_text('ok', encoding='utf-8')
    (release / 'saas-isolation-evidence.md').write_text('ok', encoding='utf-8')
    client = TestClient(create_app())
    _login(client)
    page = client.get('/backoffice/production-acceptance')
    assert page.status_code == 200
    for item in [
        '证据包预检状态',
        'saas-production-acceptance-result.md',
        'saas-release-evidence.md',
        'saas-isolation-evidence.md',
        'production_acceptance_signoffs/history.json',
        'backup-coverage.md',
        '存在',
        '缺失',
        '自动生成',
        '占位进入总包',
    ]:
        assert item in page.text
    _assert_safe(page.text)


def test_evidence_package_precheck_check_script_is_registered_and_passes():
    assert SCRIPT.exists(), 'missing evidence package precheck script'
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
    assert 'saas_production_acceptance_evidence_package_precheck: PASS' in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
