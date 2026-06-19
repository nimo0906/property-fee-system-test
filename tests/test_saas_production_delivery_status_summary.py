#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production delivery overview status summary."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_deploy import REQUIRED_DEPLOY_FILES
from server.saas_production_delivery_pages import delivery_status_summary

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_delivery_status_summary_check.py'
SCRIPT_REF = 'scripts/saas_production_delivery_status_summary_check.py'


def _login(client):
    response = client.post('/api/auth/login', json={
        'tenant_name': '交付状态物业',
        'project_name': '交付状态项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200


def _assert_safe(text):
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo', '.env']:
        assert hidden not in text


def _write_deploy_assets(root):
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


def test_delivery_status_summary_detects_ready_and_blocked_states(tmp_path):
    _write_deploy_assets(tmp_path)
    release = tmp_path / 'release'
    history_dir = release / 'production_acceptance_signoffs'
    history_dir.mkdir(parents=True)
    for name in ['saas-production-acceptance-result.md', 'saas-release-evidence.md', 'saas-isolation-evidence.md']:
        (release / name).write_text('ok', encoding='utf-8')
    (history_dir / 'history.json').write_text('{"records":[{"id":1},{"id":2}]}', encoding='utf-8')

    ready = delivery_status_summary(tmp_path)
    assert ready['decision'] == '可以进入客户签收'
    assert ready['deploy_assets'] == 'PASS'
    assert ready['evidence_missing_count'] == 0
    assert ready['signoff_history_count'] == 2
    assert ready['acceptance_result_updated_at'] != '未生成'
    assert ready['backup_coverage'] == 'PASS'

    blocked_root = tmp_path / 'blocked'
    (blocked_root / 'release').mkdir(parents=True)
    blocked = delivery_status_summary(blocked_root)
    assert blocked['decision'] == '暂缓客户签收'
    assert blocked['evidence_missing_count'] >= 3
    assert blocked['signoff_history_count'] == 0
    assert blocked['acceptance_result_updated_at'] == '未生成'


def test_production_delivery_page_shows_status_summary(tmp_path, monkeypatch):
    monkeypatch.setattr('server.saas_production_delivery_pages.ROOT', tmp_path)
    release = tmp_path / 'release'
    history_dir = release / 'production_acceptance_signoffs'
    history_dir.mkdir(parents=True)
    (release / 'saas-production-acceptance-result.md').write_text('ok', encoding='utf-8')
    (history_dir / 'history.json').write_text('{"records":[{"id":1}]}', encoding='utf-8')

    client = TestClient(create_app())
    _login(client)
    page = client.get('/backoffice/production-delivery')
    assert page.status_code == 200
    for item in [
        '交付状态汇总',
        '部署资产状态',
        '证据缺失数量',
        '签收历史数量',
        '最近验收留档',
        '备份覆盖说明',
        '当前签收建议',
        '暂缓客户签收',
    ]:
        assert item in page.text
    _assert_safe(page.text)


def test_production_delivery_status_summary_check_script_is_registered_and_passes():
    assert SCRIPT.exists(), 'missing delivery status summary check script'
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
    assert 'saas_production_delivery_status_summary_check: PASS' in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
