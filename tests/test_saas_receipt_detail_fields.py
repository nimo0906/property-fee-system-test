#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Receipt detail and export field coverage."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def _client(database_url):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '正式收据物业',
        'project_name': '正式收据项目',
        'username': 'finance',
        'role_code': 'finance',
    })
    assert response.status_code == 200
    return client


def _create_receipt(client):
    target = client.post('/api/charge-targets', json={
        'building': '商场', 'unit': '二层', 'room_number': 'S-201',
        'category': '商户', 'area': 40, 'shop_name': '收据咖啡店',
        'tenant_name': '收据承租人',
    }).json()['item']
    fee = client.post('/api/fee-types', json={
        'name': '商户物业费', 'unit_price': 3, 'billing_mode': 'area',
    }).json()['item']
    bill = client.post('/api/bills/generate', json={
        'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-04',
        'service_start': '2028-04-01', 'service_end': '2028-04-30',
    }).json()['item']
    client.post(f"/api/bills/{bill['id']}/approve", json={})
    payment = client.post('/api/payments', json={
        'bill_id': bill['id'], 'amount': 80, 'method': 'cash',
        'idempotency_key': 'RECEIPT-FIELDS-1',
    }).json()['item']
    return bill, payment


def test_receipt_detail_shows_fee_service_period_bill_amount_and_merchant_fields():
    with tempfile.TemporaryDirectory() as td:
        client = _client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        bill, payment = _create_receipt(client)

        receipt = client.get(f"/backoffice/payments/{payment['id']}/receipt")

        assert receipt.status_code == 200
        for text in [
            '收费项目', '商户物业费',
            '服务期', '2028-04-01 ~ 2028-04-30',
            '应收金额', '120.0',
            '店名', '收据咖啡店',
            '承租人', '收据承租人',
            bill['bill_number'],
        ]:
            assert text in receipt.text
        for hidden in ['tenant_id', 'project_id', 'idempotency_key', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
            assert hidden not in receipt.text


def test_receipt_csv_export_includes_fee_service_period_and_bill_amount():
    with tempfile.TemporaryDirectory() as td:
        client = _client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        _, payment = _create_receipt(client)

        exported = client.get(f"/api/exports/receipts/{payment['id']}.csv")

        assert exported.status_code == 200
        content = exported.json()['content']
        assert 'fee_name,service_start,service_end,bill_amount' in content
        for text in ['商户物业费', '2028-04-01', '2028-04-30', '120.0', '收据咖啡店', '收据承租人']:
            assert text in content
        for hidden in ['tenant_id', 'project_id', 'idempotency_key', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
            assert hidden not in content


def test_receipt_detail_print_and_csv_include_uppercase_rmb_amount():
    with tempfile.TemporaryDirectory() as td:
        client = _client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        _, payment = _create_receipt(client)

        detail = client.get(f"/backoffice/payments/{payment['id']}/receipt")
        print_page = client.get(f"/backoffice/payments/{payment['id']}/receipt/print")
        exported = client.get(f"/api/exports/receipts/{payment['id']}.csv")

        assert detail.status_code == 200
        assert print_page.status_code == 200
        assert exported.status_code == 200
        for text in ['人民币大写', '人民币捌拾元整']:
            assert text in detail.text
            assert text in print_page.text
        content = exported.json()['content']
        assert 'amount_upper' in content
        assert '人民币捌拾元整' in content
        for hidden in ['tenant_id', 'project_id', 'idempotency_key', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
            assert hidden not in detail.text
            assert hidden not in print_page.text
            assert hidden not in content
