#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Receipt print page and export field alignment tests."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def _client(database_url, tenant='打印导出物业', project='打印导出项目'):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': 'finance',
        'role_code': 'finance',
    })
    assert response.status_code == 200
    return client


def _create_receipt(client, room='P-101', key='RECEIPT-PRINT-EXPORT-1'):
    owner = client.post('/api/owners', json={
        'name': '收据业主', 'phone': '13811112222', 'owner_type': '业主',
    }).json()['item']
    target = client.post('/api/charge-targets', json={
        'owner_id': owner['id'], 'building': '商业楼', 'unit': '一层', 'room_number': room,
        'category': '商户', 'area': 50, 'shop_name': '打印咖啡', 'tenant_name': '打印承租人',
    }).json()['item']
    fee = client.post('/api/fee-types', json={
        'name': '商户物业费', 'unit_price': 4, 'billing_mode': 'area',
    }).json()['item']
    bill = client.post('/api/bills/generate', json={
        'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-06',
        'service_start': '2028-06-01', 'service_end': '2028-06-30',
    }).json()['item']
    client.post(f"/api/bills/{bill['id']}/approve", json={})
    payment = client.post('/api/payments', json={
        'bill_id': bill['id'], 'amount': 120, 'method': 'cash', 'idempotency_key': key,
    }).json()['item']
    return bill, payment


def test_receipt_print_page_is_dedicated_and_tenant_scoped():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client_a = _client(db_url)
        bill, payment = _create_receipt(client_a)

        page = client_a.get(f"/backoffice/payments/{payment['id']}/receipt/print")

        assert page.status_code == 200
        for text in [
            '收据打印', '正式收据', 'window.print()', 'receipt-print-area',
            '打印导出物业', '打印导出项目', bill['bill_number'], '商户物业费',
            '2028-06-01 ~ 2028-06-30', '200.0', '120.0', '80.0', '打印咖啡', '打印承租人',
        ]:
            assert text in page.text
        assert '返回收款列表' not in page.text
        for hidden in ['tenant_id', 'project_id', 'idempotency_key', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
            assert hidden not in page.text

        client_b = _client(db_url, tenant='其他打印物业', project='其他打印项目')
        blocked = client_b.get(f"/backoffice/payments/{payment['id']}/receipt/print")
        assert blocked.status_code == 404


def test_payment_export_aligns_with_receipt_detail_fields():
    with tempfile.TemporaryDirectory() as td:
        client = _client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        bill, payment = _create_receipt(client, room='P-201', key='RECEIPT-PRINT-EXPORT-2')

        exported = client.get('/api/exports/payments?period=2028-06')

        assert exported.status_code == 200
        content = exported.json()['content']
        assert 'fee_name,service_start,service_end,bill_amount' in content
        for text in [payment['receipt_number'], bill['bill_number'], '商户物业费', '2028-06-01', '2028-06-30', '200.0', '打印咖啡', '打印承租人']:
            assert text in content
        for hidden in ['tenant_id', 'project_id', 'idempotency_key', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
            assert hidden not in content
