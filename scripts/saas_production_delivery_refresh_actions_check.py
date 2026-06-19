#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production delivery evidence refresh actions."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app
from server.saas_production_delivery_pages import evidence_refresh_actions

SCRIPT = 'scripts/saas_production_delivery_refresh_actions_check.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    actions = evidence_refresh_actions()
    commands = [item['command'] for item in actions]
    for command in [
        'python3 scripts/saas_isolation_evidence.py',
        'python3 scripts/saas_release_evidence.py',
        'python3 scripts/saas_production_acceptance_result.py',
        'python3 scripts/saas_release_gate.py',
    ]:
        require(command in commands, f'missing command: {command}')
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '交付刷新检查物业', 'project_name': '交付刷新检查项目',
        'username': 'admin', 'role_code': 'system_admin',
    })
    require(login.status_code == 200, 'login failed')
    page = client.get('/backoffice/production-delivery')
    for item in ['证据刷新动作', *commands]:
        require(item in page.text, f'missing page item: {item}')
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id', '.env']:
        require(hidden not in page.text, f'forbidden page content: {hidden}')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('saas_production_delivery_refresh_actions_check: PASS')


if __name__ == '__main__':
    main()
