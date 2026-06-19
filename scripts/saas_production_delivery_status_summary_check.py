#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production delivery overview status summary."""

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

SCRIPT = 'scripts/saas_production_delivery_status_summary_check.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def write_deploy_assets(root):
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


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_deploy_assets(root)
        release = root / 'release'
        history = release / 'production_acceptance_signoffs'
        history.mkdir(parents=True)
        for name in ['saas-production-acceptance-result.md', 'saas-release-evidence.md', 'saas-isolation-evidence.md']:
            (release / name).write_text('ok', encoding='utf-8')
        (history / 'history.json').write_text('{"records":[{"id":1}]}', encoding='utf-8')
        ready = delivery_status_summary(root)
        require(ready['decision'] == '可以进入客户签收', 'ready decision wrong')
        blocked = delivery_status_summary(root / 'blocked')
        require(blocked['decision'] == '暂缓客户签收', 'blocked decision wrong')
        delivery_pages.ROOT = root / 'blocked'
        (delivery_pages.ROOT / 'release').mkdir(parents=True)
        client = TestClient(create_app())
        login = client.post('/api/auth/login', json={
            'tenant_name': '交付状态检查物业', 'project_name': '交付状态检查项目',
            'username': 'admin', 'role_code': 'system_admin',
        })
        require(login.status_code == 200, 'login failed')
        page = client.get('/backoffice/production-delivery')
        for item in ['交付状态汇总', '部署资产状态', '证据缺失数量', '签收历史数量', '最近验收留档', '备份覆盖说明', '当前签收建议', '暂缓客户签收']:
            require(item in page.text, f'missing status item: {item}')
        for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id', '.env']:
            require(hidden not in page.text, f'forbidden status page content: {hidden}')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('saas_production_delivery_status_summary_check: PASS')


if __name__ == '__main__':
    main()
