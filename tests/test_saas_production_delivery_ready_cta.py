#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production delivery ready state call-to-action."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_deploy import REQUIRED_DEPLOY_FILES
from server.saas_production_delivery_pages import delivery_status_summary

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_delivery_ready_cta_check.py'
SCRIPT_REF = 'scripts/saas_production_delivery_ready_cta_check.py'


def _login(client):
    response = client.post('/api/auth/login', json={
        'tenant_name': '交付签收物业',
        'project_name': '交付签收项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200


def _write_ready_assets(root):
    for name in REQUIRED_DEPLOY_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('ok\n', encoding='utf-8')
    (root / 'docker-compose.yml').write_text('''
services:
  postgres:
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U property"]
  app:
    restart: on-failure
    ports:
      - "127.0.0.1:8000:8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8000/health"]
''', encoding='utf-8')
    release = root / 'release'
    history = release / 'production_acceptance_signoffs'
    history.mkdir(parents=True)
    for name in ['saas-production-acceptance-result.md', 'saas-release-evidence.md', 'saas-isolation-evidence.md']:
        (release / name).write_text('ok', encoding='utf-8')
    (history / 'history.json').write_text('{"records":[{"id":1}]}', encoding='utf-8')


def test_ready_summary_exposes_signoff_cta(tmp_path):
    _write_ready_assets(tmp_path)
    summary = delivery_status_summary(tmp_path)
    assert summary['decision'] == '可以进入客户签收'
    assert summary['ready_message'] == '可签收检查清单已满足'
    assert summary['primary_action'] == {
        'label': '进入客户签收',
        'href': '/backoffice/production-acceptance/signoff',
    }


def test_production_delivery_page_shows_ready_cta(tmp_path, monkeypatch):
    _write_ready_assets(tmp_path)
    monkeypatch.setattr('server.saas_production_delivery_pages.ROOT', tmp_path)
    client = TestClient(create_app())
    _login(client)
    page = client.get('/backoffice/production-delivery')
    assert page.status_code == 200
    for item in ['可签收检查清单已满足', '进入客户签收', '可以进入客户签收']:
        assert item in page.text
    assert 'href="/backoffice/production-acceptance/signoff"' in page.text
    assert '暂缓客户签收' not in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo', '.env']:
        assert hidden not in page.text


def test_ready_cta_check_script_is_registered_and_passes():
    assert SCRIPT.exists(), 'missing ready cta check script'
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
    assert 'saas_production_delivery_ready_cta_check: PASS' in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
