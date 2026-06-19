#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check SaaS commercial readiness acceptance dashboard and assets."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app

REQUIRED_TEXT = [
    '商业上线总览', 'P0-1 业主与收费对象', 'P0-2 计费规则', 'P0-3 批量出账',
    'P0-4 收款欠费', 'P0-5 收据导出', 'P0-6 导入复核', 'P0-7 高风险审计',
    'P0-8 备份恢复', '租户隔离证据', '商业上线总门禁', '上线证据报告',
    'scripts/saas_commercial_readiness_check.py',
]
REQUIRED_FILES = [
    'scripts/saas_release_gate.py', 'scripts/saas_isolation_evidence.py', 'scripts/saas_release_evidence.py',
    'docs/saas-legacy-business-migration-gap.md', 'docs/saas-demo-tenant-drill.md',
]
FORBIDDEN_TEXT = ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '商业验收检查物业', 'project_name': '商业验收检查项目', 'username': 'admin', 'role_code': 'system_admin'
    })
    expect(login.status_code == 200, 'login failed')
    page = client.get('/backoffice/acceptance')
    expect(page.status_code == 200, 'acceptance page failed')
    for text in REQUIRED_TEXT:
        expect(text in page.text, f'missing readiness text: {text}')
    for text in FORBIDDEN_TEXT:
        expect(text not in page.text, f'forbidden text leaked: {text}')
    for rel in REQUIRED_FILES:
        expect((ROOT / rel).exists(), f'missing asset: {rel}')
    print('saas_commercial_readiness_check: PASS')


if __name__ == '__main__':
    main()
