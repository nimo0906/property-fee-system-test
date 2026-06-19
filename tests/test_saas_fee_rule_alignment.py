#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 fee rule alignment: area and fixed amount billing."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def login_client(database_url=None):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '规则物业', 'project_name': '规则项目', 'username': 'finance', 'role_code': 'finance'
    })
    assert response.status_code == 200
    return client


def test_repository_fee_type_supports_area_and_fixed_billing_modes():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('规则物业')
        project = repo.create_project(tenant['id'], '规则项目')
        target = repo.create_charge_target(tenant['id'], project['id'], '1栋', '1单元', '101', '居民', 80)
        area_fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 2.5, 'area')
        fixed_fee = repo.create_fee_type(tenant['id'], project['id'], '垃圾清运费', 30, 'fixed')
        assert area_fee['billing_mode'] == 'area'
        assert fixed_fee['billing_mode'] == 'fixed'
        area_bill = repo.create_bill(tenant['id'], project['id'], target['id'], area_fee['id'], '2026-09', '2026-09-01', '2026-09-30', None)
        fixed_bill = repo.create_bill(tenant['id'], project['id'], target['id'], fixed_fee['id'], '2026-09', '2026-09-01', '2026-09-30', None)
        assert area_bill['amount'] == 200.0
        assert fixed_bill['amount'] == 30.0
        listed = repo.list_fee_types(tenant['id'], project['id'])
        assert [row['billing_mode'] for row in listed] == ['area', 'fixed']
        repo.close()


def test_api_and_bill_generation_use_fixed_billing_mode_in_memory_and_persistent_modes():
    for database_url in [None, 'persistent']:
        if database_url == 'persistent':
            td = tempfile.TemporaryDirectory()
            db_url = f"sqlite:///{Path(td.name) / 'saas.sqlite3'}"
        else:
            td = None
            db_url = None
        try:
            client = login_client(db_url)
            target = client.post('/api/charge-targets', json={'building': '2栋', 'unit': '1单元', 'room_number': '201', 'category': '居民', 'area': 90}).json()['item']
            fee = client.post('/api/fee-types', json={'name': '固定服务费', 'unit_price': 45, 'billing_mode': 'fixed'})
            assert fee.status_code == 200, fee.text
            assert fee.json()['item']['billing_mode'] == 'fixed'
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee.json()['item']['id'], 'billing_period': '2026-10',
                'service_start': '2026-10-01', 'service_end': '2026-10-31',
            })
            assert bill.status_code == 200, bill.text
            assert bill.json()['item']['amount'] == 45.0
        finally:
            if td:
                td.cleanup()


def test_fee_type_page_exposes_billing_mode_and_keeps_tenant_scoped_rules():
    with tempfile.TemporaryDirectory() as td:
        client = login_client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        response = client.post('/backoffice/fee-types/create', data={'name': '固定停车费', 'unit_price': '100', 'billing_mode': 'fixed'}, follow_redirects=False)
        assert response.status_code == 303
        page = client.get('/backoffice/fee-types')
        assert page.status_code == 200
        for text in ['计费方式', '按面积', '固定金额', '固定停车费']:
            assert text in page.text
        assert '固定金额' in page.text
