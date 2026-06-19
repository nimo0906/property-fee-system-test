#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 batch billing for SaaS backoffice."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def login_client(database_url):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '批量物业', 'project_name': '批量项目', 'username': 'finance', 'role_code': 'finance'
    })
    assert response.status_code == 200
    return client


def test_repository_batch_generate_creates_one_bill_per_current_tenant_target():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant_a = repo.create_tenant('A物业')
        project_a = repo.create_project(tenant_a['id'], 'A项目')
        tenant_b = repo.create_tenant('B物业')
        project_b = repo.create_project(tenant_b['id'], 'B项目')
        repo.create_charge_target(tenant_a['id'], project_a['id'], '1栋', '1单元', '101', '居民', 80)
        repo.create_charge_target(tenant_a['id'], project_a['id'], '1栋', '1单元', '102', '居民', 90, unit_price_override=3)
        repo.create_charge_target(tenant_b['id'], project_b['id'], '2栋', '1单元', '201', '居民', 999)
        fee = repo.create_fee_type(tenant_a['id'], project_a['id'], '物业费', 2, 'area')

        result = repo.batch_generate_bills(
            tenant_a['id'], project_a['id'], fee['id'], '2027-01', '2027-01-01', '2027-01-31', actor_user_id=None
        )

        assert result['created_count'] == 2
        assert result['skipped_count'] == 0
        bills_a = repo.list_bills(tenant_a['id'], project_a['id'], '2027-01')
        bills_b = repo.list_bills(tenant_b['id'], project_b['id'], '2027-01')
        assert [bill['amount'] for bill in bills_a] == [160.0, 270.0]
        assert bills_b == []
        repo.close()


def test_repository_batch_generate_is_idempotent_for_same_period_and_fee():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('批量物业')
        project = repo.create_project(tenant['id'], '批量项目')
        repo.create_charge_target(tenant['id'], project['id'], '1栋', '1单元', '101', '居民', 80)
        fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 2, 'area')

        first = repo.batch_generate_bills(tenant['id'], project['id'], fee['id'], '2027-02', '2027-02-01', '2027-02-28')
        second = repo.batch_generate_bills(tenant['id'], project['id'], fee['id'], '2027-02', '2027-02-01', '2027-02-28')

        assert first['created_count'] == 1
        assert second['created_count'] == 0
        assert second['skipped_count'] == 1
        assert len(repo.list_bills(tenant['id'], project['id'], '2027-02')) == 1
        repo.close()


def test_api_and_backoffice_batch_generate_bills_for_selected_category():
    with tempfile.TemporaryDirectory() as td:
        client = login_client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        client.post('/api/charge-targets', json={'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80})
        client.post('/api/charge-targets', json={'building': '商场', 'unit': '一层', 'room_number': 'A-101', 'category': '商户', 'area': 50})
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2, 'billing_mode': 'area'}).json()['item']

        response = client.post('/api/bills/batch-generate', json={
            'fee_type_id': fee['id'], 'billing_period': '2027-03',
            'service_start': '2027-03-01', 'service_end': '2027-03-31', 'category': '商户',
        })
        assert response.status_code == 200, response.text
        assert response.json()['created_count'] == 1
        assert response.json()['skipped_count'] == 0
        bills = client.get('/api/bills', params={'period': '2027-03'}).json()['items']
        assert len(bills) == 1
        assert bills[0]['amount'] == 100.0

        page = client.get('/backoffice/bills')
        assert page.status_code == 200
        for text in ['批量出账', '全部类型', '仅居民', '仅商户']:
            assert text in page.text
