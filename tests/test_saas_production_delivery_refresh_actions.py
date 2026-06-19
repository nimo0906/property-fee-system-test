#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production delivery evidence refresh actions."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_production_delivery_pages import evidence_refresh_actions

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_delivery_refresh_actions_check.py'
SCRIPT_REF = 'scripts/saas_production_delivery_refresh_actions_check.py'


def _login(client):
    response = client.post('/api/auth/login', json={
        'tenant_name': '交付刷新物业',
        'project_name': '交付刷新项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200


def test_evidence_refresh_actions_show_ordered_safe_commands():
    actions = evidence_refresh_actions()
    labels = [item['label'] for item in actions]
    commands = [item['command'] for item in actions]
    assert labels == ['刷新租户隔离证据', '刷新上线证据报告', '刷新生产验收留档', '运行生产总门禁']
    assert commands == [
        'python3 scripts/saas_isolation_evidence.py',
        'python3 scripts/saas_release_evidence.py',
        'python3 scripts/saas_production_acceptance_result.py',
        'python3 scripts/saas_release_gate.py',
    ]
    for command in commands:
        assert 'POSTGRES_PASSWORD' not in command
        assert 'APP_SECRET_KEY' not in command
        assert '.env' not in command
        assert '/Users/nimo' not in command


def test_production_delivery_page_shows_refresh_actions():
    client = TestClient(create_app())
    _login(client)
    page = client.get('/backoffice/production-delivery')
    assert page.status_code == 200
    for item in [
        '证据刷新动作',
        '刷新租户隔离证据',
        '刷新上线证据报告',
        '刷新生产验收留档',
        '运行生产总门禁',
        'python3 scripts/saas_isolation_evidence.py',
        'python3 scripts/saas_release_evidence.py',
        'python3 scripts/saas_production_acceptance_result.py',
        'python3 scripts/saas_release_gate.py',
    ]:
        assert item in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo', '.env']:
        assert hidden not in page.text


def test_production_delivery_refresh_actions_check_script_is_registered_and_passes():
    assert SCRIPT.exists(), 'missing delivery refresh actions check script'
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
    assert 'saas_production_delivery_refresh_actions_check: PASS' in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
