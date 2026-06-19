#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production delivery ready signoff CTA."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app
from server.saas_deploy import REQUIRED_DEPLOY_FILES
from server.saas_production_delivery_pages import delivery_status_summary
import server.saas_production_delivery_pages as delivery_pages

SCRIPT = 'scripts/saas_production_delivery_ready_cta_check.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def write_ready_assets(root):
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


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_ready_assets(root)
        summary = delivery_status_summary(root)
        require(summary['ready_message'] == '可签收检查清单已满足', 'ready message wrong')
        require(summary['primary_action']['href'] == '/backoffice/production-acceptance/signoff', 'ready href wrong')
        delivery_pages.ROOT = root
        client = TestClient(create_app())
        login = client.post('/api/auth/login', json={
            'tenant_name': '交付签收检查物业', 'project_name': '交付签收检查项目',
            'username': 'admin', 'role_code': 'system_admin',
        })
        require(login.status_code == 200, 'login failed')
        page = client.get('/backoffice/production-delivery')
        for item in ['可签收检查清单已满足', '进入客户签收', '可以进入客户签收']:
            require(item in page.text, f'missing page item: {item}')
        require('href="/backoffice/production-acceptance/signoff"' in page.text, 'missing signoff href')
        for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id', '.env']:
            require(hidden not in page.text, f'forbidden page content: {hidden}')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('saas_production_delivery_ready_cta_check: PASS')


if __name__ == '__main__':
    main()
