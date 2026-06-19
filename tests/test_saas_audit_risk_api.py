#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 high-risk audit query API for SaaS commercial backoffice."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def login_client(database_url=None):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '审计物业', 'project_name': '审计项目', 'username': 'finance', 'role_code': 'finance'
    })
    assert response.status_code == 200
    return client


def create_payment_audit(client):
    target = client.post('/api/charge-targets', json={'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 100}).json()['item']
    fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2, 'billing_mode': 'area'}).json()['item']
    bill = client.post('/api/bills/generate', json={
        'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-07',
        'service_start': '2027-07-01', 'service_end': '2027-07-31',
    }).json()['item']
    client.post(f"/api/bills/{bill['id']}/approve")
    payment = client.post('/api/payments', json={
        'bill_id': bill['id'], 'amount': 60, 'method': 'cash', 'idempotency_key': 'audit-pay-1'
    }).json()['item']
    return payment


def test_audit_api_filters_high_risk_and_returns_sanitized_detail_in_memory_mode():
    client = login_client()
    payment = create_payment_audit(client)

    response = client.get('/api/audit-logs', params={'risk': 'high', 'action': 'payment', 'keyword': payment['receipt_number']})

    assert response.status_code == 200
    items = response.json()['items']
    assert len(items) == 1
    assert items[0]['action'] == 'payment.record'
    assert items[0]['risk_level'] == 'high'
    assert payment['receipt_number'] in str(items[0]['detail'])
    assert 'tenant_id' not in str(items[0]['detail'])
    assert 'project_id' not in str(items[0]['detail'])
    assert 'POSTGRES_PASSWORD' not in response.text
    assert 'APP_SECRET_KEY' not in response.text


def test_audit_detail_api_is_tenant_scoped_and_masks_sensitive_fields_in_persistent_mode():
    with tempfile.TemporaryDirectory() as td:
        client_a = login_client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        payment = create_payment_audit(client_a)
        logs = client_a.get('/api/audit-logs', params={'risk': 'high', 'keyword': payment['receipt_number']}).json()['items']
        log_id = logs[0]['id']

        detail = client_a.get(f'/api/audit-logs/{log_id}')
        assert detail.status_code == 200
        assert detail.json()['item']['risk_level'] == 'high'
        assert payment['receipt_number'] in str(detail.json()['item']['detail'])
        assert 'tenant_id' not in str(detail.json()['item']['detail'])
        assert 'project_id' not in str(detail.json()['item']['detail'])

        client_b = TestClient(create_app(database_url=f"sqlite:///{Path(td) / 'saas.sqlite3'}"))
        client_b.post('/api/auth/login', json={
            'tenant_name': '其他物业', 'project_name': '其他项目', 'username': 'finance_b', 'role_code': 'finance'
        })
        assert client_b.get(f'/api/audit-logs/{log_id}').status_code == 404
