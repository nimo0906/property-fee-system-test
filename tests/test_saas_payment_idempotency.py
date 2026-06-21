#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Payment idempotency safety tests."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def _client(database_url):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '幂等物业',
        'project_name': '幂等项目',
        'username': 'finance',
        'role_code': 'finance',
    })
    assert response.status_code == 200
    return client


def _seed_unpaid_bill(client, room='101', area=100):
    target = client.post('/api/charge-targets', json={
        'building': '幂等楼', 'unit': '1单元', 'room_number': room, 'category': '居民', 'area': area,
    }).json()['item']
    fee = client.post('/api/fee-types', json={'name': f'物业费{room}', 'unit_price': 2}).json()['item']
    bill = client.post('/api/bills/generate', json={
        'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-03',
        'service_start': '2028-03-01', 'service_end': '2028-03-31',
    }).json()['item']
    return client.post(f"/api/bills/{bill['id']}/approve", json={}).json()['item']


def test_api_payment_idempotency_reuses_same_request_but_rejects_changed_payload():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = _client(db_url)
        bill = _seed_unpaid_bill(client)

        first = client.post('/api/payments', json={
            'bill_id': bill['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'PAY-IDEMP-1',
        })
        repeat = client.post('/api/payments', json={
            'bill_id': bill['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'PAY-IDEMP-1',
        })
        changed = client.post('/api/payments', json={
            'bill_id': bill['id'], 'amount': 60, 'method': 'cash', 'idempotency_key': 'PAY-IDEMP-1',
        })

        assert first.status_code == 200
        assert repeat.status_code == 200
        assert repeat.json()['item']['id'] == first.json()['item']['id']
        assert changed.status_code == 400
        assert 'idempotency key conflict' in changed.text
        repo = create_saas_repository(db_url)
        tenant = repo.list_tenants()[0]
        project = repo.list_projects(tenant['id'])[0]
        payments = repo.search_payments(tenant['id'], project['id'], '', '2028-03', 1, 20)
        assert payments['total'] == 1
        assert payments['items'][0]['amount_paid'] == 50.0
        repo.close()


def test_backoffice_payment_idempotency_rejects_reused_key_for_different_bill():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = _client(db_url)
        first_bill = _seed_unpaid_bill(client, '101', 100)
        second_bill = _seed_unpaid_bill(client, '102', 120)

        first = client.post('/backoffice/payments/create', data={
            'bill_id': str(first_bill['id']), 'amount': '50', 'method': 'transfer',
            'idempotency_key': 'PAGE-IDEMP-1',
        }, follow_redirects=False)
        changed = client.post('/backoffice/payments/create', data={
            'bill_id': str(second_bill['id']), 'amount': '50', 'method': 'transfer',
            'idempotency_key': 'PAGE-IDEMP-1',
        }, follow_redirects=False)

        assert first.status_code == 303
        assert changed.status_code == 400
        assert 'idempotency key conflict' in changed.text
        repo = create_saas_repository(db_url)
        tenant = repo.list_tenants()[0]
        project = repo.list_projects(tenant['id'])[0]
        payments = repo.search_payments(tenant['id'], project['id'], '', '2028-03', 1, 20)
        assert payments['total'] == 1
        repo.close()
