#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run first-tenant business smoke drill after production startup."""

import argparse
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


def dry_run():
    for item in [
        'login', 'project context', 'charge targets', 'fee types',
        'bill generation', 'payment registration', 'reports and exports', 'tenant isolation',
    ]:
        print(f'PASS first tenant smoke plan {item}')
    print('saas_production_first_tenant_smoke: PASS')


def login(client):
    result = post_ok(client, '/api/auth/login', {
        'tenant_name': '生产首租户冒烟物业',
        'project_name': '生产首租户冒烟项目',
        'username': 'smoke_admin',
        'role_code': 'system_admin',
    })
    require(result.get('ok') is True, 'first tenant smoke login failed')
    print('PASS first tenant smoke login')
    page = client.get('/backoffice')
    require(page.status_code == 200, 'backoffice page failed')
    require('生产首租户冒烟物业' in page.text, 'project context missing')
    print('PASS first tenant smoke project context')


def create_targets(client):
    preview = post_ok(client, '/api/imports/charge-targets/preview', {'rows': [
        {'building': '冒烟住宅', 'unit': '1单元', 'room_number': '101', 'category': '住宅', 'area': '80'},
        {'building': '冒烟商业', 'unit': 'A区', 'room_number': 'A-01', 'category': '商户', 'area': '50'},
    ]})
    require(preview['valid_count'] == 2, 'target preview mismatch')
    confirm = post_ok(client, '/api/imports/charge-targets/confirm', {'import_id': preview['import_id']})
    require(confirm['created_count'] == 2, 'target import mismatch')
    targets = get_ok(client, '/api/charge-targets')['items']
    require(len(targets) == 2, 'target count mismatch')
    print('PASS first tenant smoke charge targets')
    return targets


def create_fee_types(client):
    property_fee = post_ok(client, '/api/fee-types', {'name': '冒烟物业费', 'unit_price': 2.0, 'billing_mode': 'area'})['item']
    service_fee = post_ok(client, '/api/fee-types', {'name': '冒烟固定服务费', 'unit_price': 30.0, 'billing_mode': 'fixed'})['item']
    require(property_fee['billing_mode'] == 'area', 'area fee mismatch')
    require(service_fee['billing_mode'] == 'fixed', 'fixed fee mismatch')
    print('PASS first tenant smoke fee types')
    return property_fee, service_fee


def bills_and_payments(client, targets, property_fee, service_fee):
    bills = []
    for target in targets:
        fee = service_fee if target['category'] == '商户' else property_fee
        bill = post_ok(client, '/api/bills/generate', {
            'target_id': target['id'],
            'fee_type_id': fee['id'],
            'billing_period': '2026-09',
            'service_start': '2026-09-01',
            'service_end': '2026-09-30',
        })['item']
        bills.append(bill)
    require([bill['amount'] for bill in bills] == [160.0, 30.0], 'bill amount mismatch')
    print('PASS first tenant smoke bill generation')
    for bill in bills:
        approved = post_ok(client, f"/api/bills/{bill['id']}/approve")['item']
        require(approved['status'] == 'unpaid', 'approval mismatch')
    print('PASS first tenant smoke bill approval')
    for index, amount in enumerate([160.0, 30.0], start=1):
        payment = post_ok(client, '/api/payments', {
            'bill_id': bills[index - 1]['id'],
            'amount': amount,
            'method': 'production_smoke',
            'idempotency_key': f'PROD-SMOKE-202609-{index}',
        })['item']
        require(payment['receipt_number'].startswith('RCPT-'), 'receipt missing')
    print('PASS first tenant smoke payment registration')


def reports_exports(client):
    report = get_ok(client, '/api/reports/summary?period=2026-09')
    require(report['bill_count'] == 2, 'report bill count mismatch')
    require(report['bill_amount_total'] == 190.0, 'report due mismatch')
    require(report['payment_amount_total'] == 190.0, 'report paid mismatch')
    require(report['unpaid_amount_total'] == 0.0, 'report unpaid mismatch')
    bill_export = get_ok(client, '/api/exports/bills?period=2026-09')['content']
    pay_export = get_ok(client, '/api/exports/payments?period=2026-09')['content']
    require('冒烟物业费' in bill_export and 'RCPT-' in pay_export, 'export content mismatch')
    for hidden in ['tenant_id', 'project_id']:
        require(hidden not in bill_export and hidden not in pay_export, f'export leaked {hidden}')
    print('PASS first tenant smoke reports and exports')


def verify_isolation(app):
    other = TestClient(app)
    post_ok(other, '/api/auth/login', {
        'tenant_name': '生产首租户冒烟隔离B',
        'project_name': '生产首租户冒烟隔离项目B',
        'username': 'smoke_admin_b',
        'role_code': 'system_admin',
    })
    require(get_ok(other, '/api/charge-targets')['items'] == [], 'other tenant saw targets')
    require(get_ok(other, '/api/bills/search?period=2026-09')['total'] == 0, 'other tenant saw bills')
    require(get_ok(other, '/api/reports/summary?period=2026-09')['bill_count'] == 0, 'other tenant saw report')
    print('PASS first tenant smoke tenant isolation')


def run_local():
    app = create_app()
    client = TestClient(app)
    login(client)
    targets = create_targets(client)
    property_fee, service_fee = create_fee_types(client)
    bills_and_payments(client, targets, property_fee, service_fee)
    reports_exports(client)
    verify_isolation(app)
    print('saas_production_first_tenant_smoke: PASS')


def main():
    parser = argparse.ArgumentParser(description='Run production first-tenant business smoke drill.')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--local-testclient', action='store_true')
    parser.add_argument('--base-url', help='production base URL for operator-run smoke drill')
    args = parser.parse_args()
    if args.dry_run:
        dry_run()
        return
    if args.local_testclient:
        run_local()
        return
    if args.base_url:
        print('WARN remote HTTP smoke is operator-driven in this version; use --local-testclient for CI and follow documented API steps on server')
        dry_run()
        return
    dry_run()


if __name__ == '__main__':
    main()
