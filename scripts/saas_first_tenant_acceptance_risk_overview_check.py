#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check first tenant acceptance risk status is visible from overview pages."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_first_tenant_acceptance_pages import ITEMS


FORBIDDEN = ["tenant_id", "project_id", "POSTGRES_PASSWORD", "APP_SECRET_KEY", "/Users/nimo"]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def login(tenant):
    client = TestClient(create_app())
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': '首租户项目',
        'username': 'platform_admin',
        'role_code': 'platform_admin',
    })
    require(response.status_code == 200, 'login failed')
    return client


def assert_safe(html):
    for item in FORBIDDEN:
        require(item not in html, f'forbidden page content: {item}')


def main():
    client = login('风险总览检查未完成')
    delivery = client.get('/backoffice/first-tenant-delivery-package')
    commercial = client.get('/backoffice/acceptance')
    for response in [delivery, commercial]:
        require(response.status_code == 200, 'overview page failed')
        require('验收风险' in response.text, 'missing risk status')
        require('金额配置复核未完成' in response.text, 'missing fee review risk')
        require('/backoffice/first-tenant-acceptance' in response.text, 'missing acceptance link')
        assert_safe(response.text)

    done = login('风险总览检查已完成')
    saved = done.post('/backoffice/first-tenant-acceptance', data={
        'items': ITEMS,
        'operator_name': '实施A',
        'customer_signer': '客户B',
        'notes': '全部完成',
    }, follow_redirects=True)
    require(saved.status_code == 200, 'save acceptance failed')
    for path in ['/backoffice/first-tenant-delivery-package', '/backoffice/acceptance']:
        page = done.get(path)
        require(page.status_code == 200, f'{path} failed')
        require('验收风险已解除' in page.text, f'{path} missing cleared status')
        require('全部验收项已完成' in page.text, f'{path} missing cleared detail')
        assert_safe(page.text)

    print('saas_first_tenant_acceptance_risk_overview_check: PASS')


if __name__ == '__main__':
    main()
