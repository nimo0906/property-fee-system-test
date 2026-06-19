#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check evidence summary on production acceptance page."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app
from server.saas_production_acceptance_pages import evidence_summary

SCRIPT = 'scripts/saas_production_acceptance_evidence_summary_check.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '证据摘要检查物业', 'project_name': '证据摘要检查项目',
        'username': 'admin', 'role_code': 'system_admin',
    })
    require(login.status_code == 200, 'login failed')
    page = client.get('/backoffice/production-acceptance')
    require(page.status_code == 200, 'page failed')
    for item in ['证据文件摘要', '验收留档：存在', '上线证据：存在', '隔离证据：存在', '最近生成时间']:
        require(item in page.text, f'missing summary item: {item}')
    for item in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(item not in page.text, f'forbidden page content: {item}')
    print('PASS production acceptance evidence summary page')
    missing = evidence_summary(ROOT / '.missing-summary-root')
    require(all(row['status'] == '缺失' for row in missing), 'missing files should be reported')
    require(all(row['updated_at'] == '未生成' for row in missing), 'missing files should have no timestamp')
    print('PASS production acceptance evidence summary helper')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('PASS production acceptance evidence summary registry')
    print('saas_production_acceptance_evidence_summary_check: PASS')


if __name__ == '__main__':
    main()
