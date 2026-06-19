#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production acceptance signoff form and exports."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_acceptance_signoff_check.py'
SCRIPT_REF = 'scripts/saas_production_acceptance_signoff_check.py'


def _login(client, role='system_admin'):
    return client.post('/api/auth/login', json={
        'tenant_name': '生产签收物业',
        'project_name': '生产签收项目',
        'username': 'admin',
        'role_code': role,
    })


def _assert_safe(text):
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo']:
        assert hidden not in text


def test_production_acceptance_page_links_signoff_form_and_exports():
    client = TestClient(create_app())
    assert _login(client).status_code == 200
    page = client.get('/backoffice/production-acceptance')
    assert page.status_code == 200
    for item in [
        '填写生产验收签收信息',
        '/backoffice/production-acceptance/signoff',
        '/backoffice/production-acceptance/signoff/print',
        '/backoffice/production-acceptance/signoff/download.md',
    ]:
        assert item in page.text
    _assert_safe(page.text)


def test_production_acceptance_signoff_can_save_preview_print_and_download(tmp_path, monkeypatch):
    monkeypatch.setattr('server.saas_production_acceptance_pages.ROOT', tmp_path)
    (tmp_path / 'release').mkdir()
    client = TestClient(create_app())
    assert _login(client).status_code == 200

    form = client.get('/backoffice/production-acceptance/signoff')
    assert form.status_code == 200
    for item in ['生产验收签收表', '执行人', '服务器域名', '验收结论', '客户签收人', '实施人员', '保存并生成验收留档']:
        assert item in form.text
    _assert_safe(form.text)

    saved = client.post('/backoffice/production-acceptance/signoff', data={
        'operator_name': '实施A',
        'server_domain': 'saas.example.com',
        'acceptance_status': 'PASS',
        'customer_signer': '客户B',
        'implementation_signer': '实施C',
        'signoff_date': '2026-06-19',
        'notes': '现场验收通过',
    }, follow_redirects=False)
    assert saved.status_code == 303
    assert saved.headers['location'].startswith('/backoffice/production-acceptance/signoff?')

    report = tmp_path / 'release' / 'saas-production-acceptance-result.md'
    assert report.exists()
    text = report.read_text(encoding='utf-8')
    for item in ['执行人：实施A', '服务器域名：saas.example.com', '验收结论：PASS', '客户签收人：客户B', '实施人员签字：实施C', '签收日期：2026-06-19', '现场验收通过']:
        assert item in text
    _assert_safe(text)

    preview = client.get('/backoffice/production-acceptance/evidence/acceptance-result')
    assert preview.status_code == 200
    assert '实施A' in preview.text
    assert 'saas.example.com' in preview.text

    printable = client.get('/backoffice/production-acceptance/signoff/print')
    assert printable.status_code == 200
    assert '生产验收签收表（打印版）' in printable.text
    assert 'window.print' in printable.text
    assert '客户签字' in printable.text
    _assert_safe(printable.text)

    download = client.get('/backoffice/production-acceptance/signoff/download.md')
    assert download.status_code == 200
    assert 'text/markdown' in download.headers.get('content-type', '')
    assert 'attachment;' in download.headers.get('content-disposition', '')
    assert 'saas-production-acceptance-result.md' in download.headers.get('content-disposition', '')
    assert '执行人：实施A' in download.text
    _assert_safe(download.text)


def test_production_acceptance_signoff_is_admin_scoped_and_registered():
    non_admin = TestClient(create_app())
    assert _login(non_admin, role='executive').status_code == 200
    assert non_admin.get('/backoffice/production-acceptance/signoff').status_code == 403

    assert SCRIPT.exists(), 'missing production acceptance signoff check script'
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
    assert 'saas_production_acceptance_signoff_check: PASS' in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
