#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 receipt and export alignment for SaaS commercial backoffice."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def login_client(database_url):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '导出物业', 'project_name': '导出项目', 'username': 'finance', 'role_code': 'finance'
    })
    assert response.status_code == 200
    return client


def setup_paid_bill(client):
    owner = client.post('/api/owners', json={'name': '张三', 'phone': '13800000000', 'owner_type': '业主'}).json()['item']
    target = client.post('/api/charge-targets', json={
        'owner_id': owner['id'], 'building': '1栋', 'unit': '1单元', 'room_number': '101',
        'category': '居民', 'area': 100,
    }).json()['item']
    fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2, 'billing_mode': 'area'}).json()['item']
    bill = client.post('/api/bills/generate', json={
        'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-06',
        'service_start': '2027-06-01', 'service_end': '2027-06-30',
    }).json()['item']
    client.post(f"/api/bills/{bill['id']}/approve")
    payment = client.post('/api/payments', json={
        'bill_id': bill['id'], 'amount': 80, 'method': 'cash', 'idempotency_key': 'export-pay-1'
    }).json()['item']
    return bill, payment


def test_bill_and_payment_exports_include_business_fields_without_internal_ids():
    with tempfile.TemporaryDirectory() as td:
        client = login_client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        bill, payment = setup_paid_bill(client)

        bills = client.get('/api/exports/bills', params={'period': '2027-06'}).json()['content']
        payments = client.get('/api/exports/payments', params={'period': '2027-06'}).json()['content']

        assert 'bill_number,billing_period,building,unit,room_number,shop_name,tenant_name,owner_name,fee_name,amount,paid_amount,unpaid_amount,status' in bills
        assert 'SaaS-' in bills and '张三' in bills and '101' in bills and ',80.0,120.0,' in bills
        assert 'tenant_id' not in bills and 'project_id' not in bills
        assert 'receipt_number,bill_number,billing_period,building,unit,room_number,owner_name,amount_paid,method' in payments
        assert payment['receipt_number'] in payments and '张三' in payments and '101' in payments
        assert 'tenant_id' not in payments and 'project_id' not in payments


def test_receipt_page_shows_project_target_owner_and_remaining_arrears():
    with tempfile.TemporaryDirectory() as td:
        client = login_client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        _bill, payment = setup_paid_bill(client)

        page = client.get(f"/backoffice/payments/{payment['id']}/receipt")
        assert page.status_code == 200
        for text in ['导出物业', '导出项目', '张三', '1栋 1单元 101', '欠费余额', '120.0']:
            assert text in page.text
        for text in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
            assert text not in page.text
