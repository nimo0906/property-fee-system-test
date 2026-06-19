#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 payment and arrears alignment for SaaS billing."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def login_client(database_url):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '收款物业', 'project_name': '收款项目', 'username': 'finance', 'role_code': 'finance'
    })
    assert response.status_code == 200
    return client


def test_repository_list_bills_includes_paid_and_unpaid_amounts_after_partial_payment():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('收款物业')
        project = repo.create_project(tenant['id'], '收款项目')
        target = repo.create_charge_target(tenant['id'], project['id'], '1栋', '1单元', '101', '居民', 100)
        fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 2, 'area')
        bill = repo.create_bill(tenant['id'], project['id'], target['id'], fee['id'], '2027-04', '2027-04-01', '2027-04-30', None)
        repo.approve_bill(tenant['id'], project['id'], bill['id'])

        repo.create_payment(tenant['id'], project['id'], bill['id'], 80, 'cash', 'payment-1')

        listed = repo.list_bills(tenant['id'], project['id'], '2027-04')
        searched = repo.search_bills(tenant['id'], project['id'], '', '2027-04', None, 1, 20)['items']
        assert listed[0]['paid_amount'] == 80.0
        assert listed[0]['unpaid_amount'] == 120.0
        assert listed[0]['status'] == 'partial'
        assert searched[0]['paid_amount'] == 80.0
        assert searched[0]['unpaid_amount'] == 120.0
        repo.close()


def test_api_bills_and_backoffice_payment_form_show_remaining_arrears():
    with tempfile.TemporaryDirectory() as td:
        client = login_client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        target = client.post('/api/charge-targets', json={
            'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 100,
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2, 'billing_mode': 'area'}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-05',
            'service_start': '2027-05-01', 'service_end': '2027-05-31',
        }).json()['item']
        client.post(f"/api/bills/{bill['id']}/approve")
        payment = client.post('/api/payments', json={
            'bill_id': bill['id'], 'amount': 50, 'method': 'cash', 'idempotency_key': 'pay-api-1',
        })
        assert payment.status_code == 200, payment.text

        bills = client.get('/api/bills', params={'period': '2027-05'}).json()['items']
        assert bills[0]['paid_amount'] == 50.0
        assert bills[0]['unpaid_amount'] == 150.0
        page = client.get('/backoffice/payments')
        assert page.status_code == 200
        for text in ['已收', '欠费', '150.0']:
            assert text in page.text


def test_repository_rejects_payment_amount_above_remaining_arrears():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('超收物业')
        project = repo.create_project(tenant['id'], '超收项目')
        target = repo.create_charge_target(tenant['id'], project['id'], '1栋', '1单元', '101', '居民', 100)
        fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 2, 'area')
        bill = repo.create_bill(tenant['id'], project['id'], target['id'], fee['id'], '2027-09', '2027-09-01', '2027-09-30', None)
        repo.approve_bill(tenant['id'], project['id'], bill['id'])
        repo.create_payment(tenant['id'], project['id'], bill['id'], 150, 'cash', 'overpay-base')

        try:
            repo.create_payment(tenant['id'], project['id'], bill['id'], 60, 'cash', 'overpay-too-much')
        except Exception as exc:
            assert 'remaining' in str(exc).lower() or '欠费' in str(exc)
        else:
            raise AssertionError('payment above remaining arrears was allowed')

        listed = repo.list_bills(tenant['id'], project['id'], '2027-09')
        assert listed[0]['paid_amount'] == 150.0
        assert listed[0]['unpaid_amount'] == 50.0
        assert len(repo.search_payments(tenant['id'], project['id'], '', '2027-09', 1, 20)['items']) == 1
        repo.close()


def test_api_and_backoffice_reject_payment_amount_above_remaining_arrears():
    with tempfile.TemporaryDirectory() as td:
        client = login_client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        target = client.post('/api/charge-targets', json={
            'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 100,
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2, 'billing_mode': 'area'}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2027-10',
            'service_start': '2027-10-01', 'service_end': '2027-10-31',
        }).json()['item']
        client.post(f"/api/bills/{bill['id']}/approve")
        assert client.post('/api/payments', json={
            'bill_id': bill['id'], 'amount': 180, 'method': 'cash', 'idempotency_key': 'api-overpay-base',
        }).status_code == 200

        api_overpay = client.post('/api/payments', json={
            'bill_id': bill['id'], 'amount': 30, 'method': 'cash', 'idempotency_key': 'api-overpay-too-much',
        })
        assert api_overpay.status_code == 400
        assert 'remaining' in api_overpay.text.lower() or '欠费' in api_overpay.text

        page_overpay = client.post('/backoffice/payments/create', data={
            'bill_id': str(bill['id']), 'amount': '30', 'method': 'cash', 'idempotency_key': 'page-overpay-too-much',
        }, follow_redirects=False)
        assert page_overpay.status_code == 400
        assert 'remaining' in page_overpay.text.lower() or '欠费' in page_overpay.text

        bills = client.get('/api/bills', params={'period': '2027-10'}).json()['items']
        assert bills[0]['paid_amount'] == 180.0
        assert bills[0]['unpaid_amount'] == 20.0
