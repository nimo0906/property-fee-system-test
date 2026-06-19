#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production delivery missing evidence details."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_production_delivery_pages import delivery_status_summary

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_delivery_missing_evidence_details_check.py'
SCRIPT_REF = 'scripts/saas_production_delivery_missing_evidence_details_check.py'


def _login(client):
    response = client.post('/api/auth/login', json={
        'tenant_name': '交付明细物业',
        'project_name': '交付明细项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200


def test_delivery_status_summary_lists_each_missing_evidence_file(tmp_path):
    summary = delivery_status_summary(tmp_path)
    labels = [item['label'] for item in summary['blockers']]
    assert '缺少生产验收留档' in labels
    assert '缺少上线证据报告' in labels
    assert '缺少租户隔离证据' in labels
    assert '缺少签收历史' in labels
    assert '验收证据未补齐' not in labels
    hrefs = {item['label']: item['href'] for item in summary['blockers']}
    assert hrefs['缺少生产验收留档'] == '/backoffice/production-acceptance/signoff'
    assert hrefs['缺少上线证据报告'] == '/backoffice/production-acceptance'
    assert hrefs['缺少租户隔离证据'] == '/backoffice/production-acceptance'
    assert hrefs['缺少签收历史'] == '/backoffice/production-acceptance/signoff'


def test_production_delivery_page_shows_missing_evidence_details(tmp_path, monkeypatch):
    monkeypatch.setattr('server.saas_production_delivery_pages.ROOT', tmp_path)
    client = TestClient(create_app())
    _login(client)
    page = client.get('/backoffice/production-delivery')
    assert page.status_code == 200
    for item in ['缺少生产验收留档', '缺少上线证据报告', '缺少租户隔离证据', '缺少签收历史']:
        assert item in page.text
    assert '验收证据未补齐</td>' not in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo', '.env']:
        assert hidden not in page.text


def test_missing_evidence_details_check_script_is_registered_and_passes():
    assert SCRIPT.exists(), 'missing evidence detail check script'
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
    assert 'saas_production_delivery_missing_evidence_details_check: PASS' in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
