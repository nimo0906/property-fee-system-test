#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check first tenant acceptance records persist in system-scoped storage."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_first_tenant_acceptance_pages import ITEMS
from server.saas_first_tenant_acceptance_store import FirstTenantAcceptanceStore

FORBIDDEN = ["tenant_id", "project_id", "POSTGRES_PASSWORD", "APP_SECRET_KEY", "/Users/nimo"]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def login(client, tenant):
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': '持久化项目',
        'username': 'platform_admin',
        'role_code': 'platform_admin',
    })
    require(response.status_code == 200, 'login failed')


def assert_safe(text):
    for item in FORBIDDEN:
        require(item not in text, f'forbidden page content: {item}')


def main():
    with tempfile.TemporaryDirectory() as td:
        store = FirstTenantAcceptanceStore(td)
        client = TestClient(create_app(acceptance_store=store))
        login(client, '验收持久化检查')
        saved = client.post('/backoffice/first-tenant-acceptance', data={
            'items': ITEMS,
            'operator_name': '实施A',
            'customer_signer': '客户B',
            'notes': '持久化检查完成',
        }, follow_redirects=True)
        require(saved.status_code == 200, 'save failed')
        require((Path(td) / 'system' / 'first_tenant_acceptance' / 'records.json').exists(), 'store file missing')

        restarted = TestClient(create_app(acceptance_store=store))
        login(restarted, '验收持久化检查')
        page = restarted.get('/backoffice/first-tenant-acceptance')
        require(page.status_code == 200, 'page failed after restart')
        for text in ['实施A', '客户B', '持久化检查完成', '验收风险已解除']:
            require(text in page.text, f'missing persisted text: {text}')
        assert_safe(page.text)

    print('saas_first_tenant_acceptance_persistence_check: PASS')


if __name__ == '__main__':
    main()
