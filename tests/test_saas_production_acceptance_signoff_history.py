#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production acceptance signoff history is traceable and downloadable."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_acceptance_signoff_history_check.py'
SCRIPT_REF = 'scripts/saas_production_acceptance_signoff_history_check.py'


def _login(client, role='system_admin'):
    response = client.post('/api/auth/login', json={
        'tenant_name': '生产签收历史物业',
        'project_name': '生产签收历史项目',
        'username': 'admin',
        'role_code': role,
    })
    assert response.status_code == 200


def _post_signoff(client, operator, signer, note):
    return client.post('/backoffice/production-acceptance/signoff', data={
        'operator_name': operator,
        'server_domain': 'saas-history.example.com',
        'acceptance_status': 'PASS',
        'customer_signer': signer,
        'implementation_signer': f'{operator}签字',
        'signoff_date': '2026-06-19',
        'notes': note,
    }, follow_redirects=False)


def _assert_safe(text):
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo']:
        assert hidden not in text


def test_multiple_production_signoffs_are_saved_as_history_and_downloadable(tmp_path, monkeypatch):
    monkeypatch.setattr('server.saas_production_acceptance_pages.ROOT', tmp_path)
    (tmp_path / 'release').mkdir()
    client = TestClient(create_app())
    _login(client)

    assert _post_signoff(client, '实施A', '客户A', '第一次签收').status_code == 303
    assert _post_signoff(client, '实施B', '客户B', '第二次签收').status_code == 303

    history_file = tmp_path / 'release' / 'production_acceptance_signoffs' / 'history.json'
    assert history_file.exists()
    history_text = history_file.read_text(encoding='utf-8')
    assert '第一次签收' in history_text
    assert '第二次签收' in history_text
    _assert_safe(history_text)

    page = client.get('/backoffice/production-acceptance/signoff')
    assert page.status_code == 200
    for item in ['签收历史记录', '实施A', '客户A', '第一次签收', '实施B', '客户B', '第二次签收', '/backoffice/production-acceptance/signoff/history/1/download.md', '/backoffice/production-acceptance/signoff/history/2/download.md']:
        assert item in page.text
    _assert_safe(page.text)

    latest = (tmp_path / 'release' / 'saas-production-acceptance-result.md').read_text(encoding='utf-8')
    assert '第二次签收' in latest
    assert '第一次签收' not in latest

    first = client.get('/backoffice/production-acceptance/signoff/history/1/download.md')
    second = client.get('/backoffice/production-acceptance/signoff/history/2/download.md')
    assert first.status_code == 200
    assert second.status_code == 200
    assert 'attachment;' in first.headers.get('content-disposition', '')
    assert 'saas-production-acceptance-signoff-1.md' in first.headers.get('content-disposition', '')
    assert '第一次签收' in first.text
    assert '第二次签收' not in first.text
    assert '第二次签收' in second.text
    _assert_safe(first.text)
    _assert_safe(second.text)
    assert client.get('/backoffice/production-acceptance/signoff/history/999/download.md').status_code == 404


def test_production_acceptance_signoff_history_is_admin_scoped_and_registered(tmp_path, monkeypatch):
    monkeypatch.setattr('server.saas_production_acceptance_pages.ROOT', tmp_path)
    (tmp_path / 'release').mkdir()
    client = TestClient(create_app())
    _login(client)
    assert _post_signoff(client, '实施A', '客户A', '历史权限').status_code == 303

    non_admin = TestClient(create_app())
    _login(non_admin, role='executive')
    assert non_admin.get('/backoffice/production-acceptance/signoff/history/1/download.md').status_code == 403

    assert SCRIPT.exists(), 'missing production acceptance signoff history check script'
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
    assert 'saas_production_acceptance_signoff_history_check: PASS' in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
