#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production delivery blocked action links."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app
from server.saas_production_delivery_pages import delivery_status_summary
import server.saas_production_delivery_pages as delivery_pages

SCRIPT = 'scripts/saas_production_delivery_action_links_check.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        summary = delivery_status_summary(root)
        require(summary['decision'] == '暂缓客户签收', 'blocked decision wrong')
        labels = {item['label']: item['href'] for item in summary['blockers']}
        require(labels.get('部署资产未通过') == '/backoffice/deploy-checklist', 'missing deploy repair link')
        require(labels.get('缺少上线证据报告') == '/backoffice/production-acceptance', 'missing release evidence repair link')
        require(labels.get('缺少租户隔离证据') == '/backoffice/production-acceptance', 'missing isolation evidence repair link')
        require(labels.get('缺少签收历史') == '/backoffice/production-acceptance/signoff', 'missing signoff repair link')
        require(labels.get('缺少生产验收留档') == '/backoffice/production-acceptance/signoff', 'missing result repair link')
        delivery_pages.ROOT = root
        client = TestClient(create_app())
        login = client.post('/api/auth/login', json={
            'tenant_name': '交付修复检查物业', 'project_name': '交付修复检查项目',
            'username': 'admin', 'role_code': 'system_admin',
        })
        require(login.status_code == 200, 'login failed')
        page = client.get('/backoffice/production-delivery')
        for item in ['暂缓原因和修复入口', *labels.keys(), '去处理']:
            require(item in page.text, f'missing page text: {item}')
        for href in labels.values():
            require(f'href="{href}"' in page.text, f'missing page href: {href}')
        for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id', '.env']:
            require(hidden not in page.text, f'forbidden status page content: {hidden}')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('saas_production_delivery_action_links_check: PASS')


if __name__ == '__main__':
    main()
