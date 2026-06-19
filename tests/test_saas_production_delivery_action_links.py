#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production delivery blocked action links."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_production_delivery_pages import delivery_status_summary

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_delivery_action_links_check.py'
SCRIPT_REF = 'scripts/saas_production_delivery_action_links_check.py'


def _login(client):
    response = client.post('/api/auth/login', json={
        'tenant_name': '交付修复物业',
        'project_name': '交付修复项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200


def test_delivery_status_summary_explains_blockers_with_action_links(tmp_path):
    summary = delivery_status_summary(tmp_path)
    assert summary['decision'] == '暂缓客户签收'
    blockers = summary['blockers']
    assert {'label': '部署资产未通过', 'href': '/backoffice/deploy-checklist'} in blockers
    assert {'label': '缺少上线证据报告', 'href': '/backoffice/production-acceptance'} in blockers
    assert {'label': '缺少租户隔离证据', 'href': '/backoffice/production-acceptance'} in blockers
    assert {'label': '缺少签收历史', 'href': '/backoffice/production-acceptance/signoff'} in blockers
    assert {'label': '缺少生产验收留档', 'href': '/backoffice/production-acceptance/signoff'} in blockers


def test_production_delivery_page_shows_blocked_repair_links(tmp_path, monkeypatch):
    monkeypatch.setattr('server.saas_production_delivery_pages.ROOT', tmp_path)
    client = TestClient(create_app())
    _login(client)
    page = client.get('/backoffice/production-delivery')
    assert page.status_code == 200
    for item in ['暂缓原因和修复入口', '部署资产未通过', '缺少上线证据报告', '缺少租户隔离证据', '缺少签收历史', '缺少生产验收留档']:
        assert item in page.text
    for href in ['/backoffice/deploy-checklist', '/backoffice/production-acceptance', '/backoffice/production-acceptance/signoff']:
        assert f'href="{href}"' in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo', '.env']:
        assert hidden not in page.text


def test_production_delivery_action_links_check_script_is_registered_and_passes():
    assert SCRIPT.exists(), 'missing delivery action links check script'
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
    assert 'saas_production_delivery_action_links_check: PASS' in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
