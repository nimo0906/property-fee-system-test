#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run commercial delivery drill from an empty SaaS tenant."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def post_ok(client, path, payload=None):
    response = client.post(path, json=payload or {})
    require(response.status_code == 200, f'{path} failed: {response.text}')
    return response.json()


def get_ok(client, path):
    response = client.get(path)
    require(response.status_code == 200, f'{path} failed: {response.text}')
    return response.json()


def login_empty_tenant(client):
    result = post_ok(client, '/api/auth/login', {
        'tenant_name': '交付演示物业公司',
        'project_name': '交付演示项目',
        'username': 'delivery_admin',
        'role_code': 'system_admin',
    })
    require(result.get('ok') is True, 'commercial delivery login failed')
    print('PASS commercial delivery tenant login')
    page = client.get('/backoffice')
    require(page.status_code == 200, 'backoffice page failed')
    require('交付演示物业公司' in page.text and '交付演示项目' in page.text, 'project context mismatch')
    print('PASS commercial delivery project context')


def create_targets(client):
    preview = post_ok(client, '/api/imports/charge-targets/preview', {'rows': [
        {'building': '交付住宅', 'unit': '1单元', 'room_number': '101', 'category': '住宅', 'area': '80'},
        {'building': '交付住宅', 'unit': '1单元', 'room_number': '102', 'category': '住宅', 'area': '100'},
        {'building': '交付商业', 'unit': 'A区', 'room_number': 'A-01', 'category': '商户', 'area': '50'},
    ]})
    require(preview['valid_count'] == 3, 'target preview mismatch')
    confirm = post_ok(client, '/api/imports/charge-targets/confirm', {'import_id': preview['import_id']})
    require(confirm['created_count'] == 3, 'target import mismatch')
    targets = get_ok(client, '/api/charge-targets')['items']
    require(len(targets) == 3, 'target count mismatch')
    print('PASS commercial delivery charge targets')
    return targets


def create_fee_types(client):
    property_fee = post_ok(client, '/api/fee-types', {
        'name': '交付物业费', 'unit_price': 2.0, 'billing_mode': 'area'
    })['item']
    fixed_fee = post_ok(client, '/api/fee-types', {
        'name': '交付固定服务费', 'unit_price': 30.0, 'billing_mode': 'fixed'
    })['item']
    require(property_fee['billing_mode'] == 'area', 'area fee mismatch')
    require(fixed_fee['billing_mode'] == 'fixed', 'fixed fee mismatch')
    print('PASS commercial delivery fee types')
    return property_fee, fixed_fee


def generate_and_approve_bills(client, targets, property_fee, fixed_fee):
    bills = []
    for target in targets:
        fee = fixed_fee if target['category'] == '商户' else property_fee
        bill = post_ok(client, '/api/bills/generate', {
            'target_id': target['id'],
            'fee_type_id': fee['id'],
            'billing_period': '2026-08',
            'service_start': '2026-08-01',
            'service_end': '2026-08-31',
        })['item']
        require(bill['status'] == 'pending_review', 'bill should be pending review')
        bills.append(bill)
    require([bill['amount'] for bill in bills] == [160.0, 200.0, 30.0], 'bill amounts mismatch')
    print('PASS commercial delivery bill generation')
    for bill in bills:
        approved = post_ok(client, f"/api/bills/{bill['id']}/approve")['item']
        require(approved['status'] == 'unpaid', 'approval status mismatch')
    print('PASS commercial delivery bill approval')
    return bills


def collect_payments(client, bills):
    for index, amount in enumerate([160.0, 80.0, 30.0], start=1):
        payment = post_ok(client, '/api/payments', {
            'bill_id': bills[index - 1]['id'],
            'amount': amount,
            'method': 'delivery_demo',
            'idempotency_key': f'DELIVERY-202608-{index}',
        })['item']
        require(payment['receipt_number'].startswith('RCPT-'), 'receipt number mismatch')
    print('PASS commercial delivery payments')


def verify_reports_exports_ops(client):
    report = get_ok(client, '/api/reports/summary?period=2026-08')
    require(report['bill_count'] == 3, 'report bill count mismatch')
    require(report['bill_amount_total'] == 390.0, 'report due mismatch')
    require(report['payment_amount_total'] == 270.0, 'report paid mismatch')
    require(report['unpaid_amount_total'] == 120.0, 'report unpaid mismatch')
    print('PASS commercial delivery reports')
    bill_export = get_ok(client, '/api/exports/bills?period=2026-08')
    pay_export = get_ok(client, '/api/exports/payments?period=2026-08')
    require('交付物业费' in bill_export['content'], 'bill export missing fee')
    require('RCPT-' in pay_export['content'], 'payment export missing receipt')
    for hidden in ['tenant_id', 'project_id']:
        require(hidden not in bill_export['content'], f'bill export leaked {hidden}')
        require(hidden not in pay_export['content'], f'payment export leaked {hidden}')
    print('PASS commercial delivery exports')
    backup = post_ok(client, '/api/backups/create')['item']
    drill = post_ok(client, '/api/restore-drills', {'backup_id': backup['backup_id'], 'scope': 'database'})['item']
    require(drill['scope'] == 'database', 'restore drill scope mismatch')
    print('PASS commercial delivery backup restore drill')


def run_one_tenant(client):
    login_empty_tenant(client)
    targets = create_targets(client)
    property_fee, fixed_fee = create_fee_types(client)
    bills = generate_and_approve_bills(client, targets, property_fee, fixed_fee)
    collect_payments(client, bills)
    verify_reports_exports_ops(client)


def verify_isolation(app):
    other = TestClient(app)
    post_ok(other, '/api/auth/login', {
        'tenant_name': '交付演示隔离公司B',
        'project_name': '交付演示隔离项目B',
        'username': 'delivery_admin_b',
        'role_code': 'system_admin',
    })
    require(get_ok(other, '/api/charge-targets')['items'] == [], 'other tenant saw targets')
    require(get_ok(other, '/api/bills/search?period=2026-08')['total'] == 0, 'other tenant saw bills')
    require(get_ok(other, '/api/reports/summary?period=2026-08')['bill_count'] == 0, 'other tenant saw report')
    print('PASS commercial delivery isolation')


def main():
    app = create_app()
    client = TestClient(app)
    run_one_tenant(client)
    verify_isolation(app)
    print('saas_commercial_delivery_drill: PASS')


if __name__ == '__main__':
    main()
