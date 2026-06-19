#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production acceptance result center page."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app

SCRIPT = 'scripts/saas_production_acceptance_page_check.py'
REQUIRED = [
    '生产验收结果中心', '一键验收总入口', 'scripts/saas_production_acceptance_gate.py',
    '验收结果留档文件', 'release/saas-production-acceptance-result.md',
    '上线证据报告', 'release/saas-release-evidence.md', '租户隔离证据',
    'release/saas-isolation-evidence.md', '首租户冒烟说明',
    'scripts/saas_production_first_tenant_smoke.py', '客户上传数据与系统自身数据隔离', '失败即停止交付',
]
FORBIDDEN = ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def login(client):
    response = client.post('/api/auth/login', json={
        'tenant_name': '生产验收页面检查物业', 'project_name': '生产验收页面检查项目',
        'username': 'admin', 'role_code': 'system_admin',
    })
    require(response.status_code == 200, 'login failed')


def main():
    client = TestClient(create_app())
    login(client)
    page = client.get('/backoffice/production-acceptance')
    require(page.status_code == 200, 'production acceptance page failed')
    for item in REQUIRED:
        require(item in page.text, f'missing page item: {item}')
    for item in FORBIDDEN:
        require(item not in page.text, f'forbidden page content: {item}')
    print('PASS production acceptance result page')
    deploy = client.get('/backoffice/deploy-checklist')
    acceptance = client.get('/backoffice/acceptance')
    for html in [deploy.text, acceptance.text]:
        require('/backoffice/production-acceptance' in html, 'missing production acceptance link')
        require('生产验收结果中心' in html, 'missing production acceptance label')
    print('PASS production acceptance result page links')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('PASS production acceptance result page registry')
    print('saas_production_acceptance_page_check: PASS')


if __name__ == '__main__':
    main()
