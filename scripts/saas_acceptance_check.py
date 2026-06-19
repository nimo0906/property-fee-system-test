#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end acceptance check for SaaS cloud backoffice slice."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_acceptance_boundary import (
    run_account_boundary_acceptance,
    run_import_upload_acceptance,
    run_isolation_acceptance,
    run_storage_boundary_acceptance,
)


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def run_acceptance(label, database_url=None):
    app = create_app(database_url=database_url)
    client = TestClient(app)
    login = client.post('/api/auth/login', json={
        'tenant_name': f'验收物业-{label}',
        'project_name': f'验收项目-{label}',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    expect(login.status_code == 200, f'login failed: {login.text}')
    user = client.post('/api/users', json={'username': f'finance_accept_{label}', 'role_code': 'finance'})
    expect(user.status_code == 200, f'user create failed: {user.text}')
    fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5}).json()['item']
    preview = client.post('/api/imports/charge-targets/preview', json={'rows': [
        {'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '80'},
        {'building': '1栋', 'unit': '1单元', 'room_number': '', 'category': '居民', 'area': '80'},
    ]})
    expect(preview.status_code == 200 and preview.json()['valid_count'] == 1, 'import preview failed')
    review = client.get(f"/api/imports/{preview.json()['import_id']}/review")
    expect(review.status_code == 200 and review.json()['error_count'] == 1, 'import review failed')
    confirm = client.post('/api/imports/charge-targets/confirm', json={'import_id': preview.json()['import_id']})
    expect(confirm.status_code == 200 and confirm.json()['created_count'] == 1, 'import confirm failed')
    target = client.get('/api/charge-targets').json()['items'][0]
    bill = client.post('/api/bills/generate', json={
        'target_id': target['id'],
        'fee_type_id': fee['id'],
        'billing_period': '2026-06',
        'service_start': '2026-06-01',
        'service_end': '2026-06-30',
    }).json()['item']
    expect(bill['status'] == 'pending_review', 'bill should require review')
    pending_payment = client.post('/api/payments', json={'bill_id': bill['id'], 'amount': 50, 'method': 'cash'})
    expect(pending_payment.status_code == 403, 'pending bill accepted payment')
    approve = client.post(f"/api/bills/{bill['id']}/approve", json={})
    expect(approve.status_code == 200, 'bill approve failed')
    payment = client.post('/api/payments', json={
        'bill_id': bill['id'],
        'amount': 50,
        'method': 'cash',
        'idempotency_key': f'ACCEPT-PAY-{label}',
    })
    expect(payment.status_code == 200 and payment.json()['item']['receipt_number'].startswith('RCPT-'), 'payment failed')
    expect(client.get('/api/bills/search?keyword=101').json()['total'] == 1, 'bill search failed')
    expect(client.get('/api/payments?keyword=RCPT').json()['total'] == 1, 'payment search failed')
    report = client.get('/api/reports/summary?period=2026-06').json()
    expect(report['bill_amount_total'] == 200.0, 'bill total mismatch')
    expect(report['payment_amount_total'] == 50.0, 'payment total mismatch')
    expect(report['unpaid_amount_total'] == 150.0, 'unpaid total mismatch')
    expect('SaaS' in client.get('/api/exports/bills?period=2026-06').json()['content'] or 'BILL' in client.get('/api/exports/bills?period=2026-06').json()['content'], 'bill export failed')
    expect('RCPT' in client.get('/api/exports/payments?period=2026-06').json()['content'], 'payment export failed')
    backup = client.post('/api/backups/create', json={})
    expect(backup.status_code == 200, 'backup marker failed')
    drill = client.post('/api/restore-drills', json={'backup_id': backup.json()['item']['backup_id'], 'scope': 'database'})
    expect(drill.status_code == 200, 'restore drill failed')
    actions = [row['action'] for row in client.get('/api/audit-logs').json()['items']]
    for action in ['bill.generate', 'bill.approve', 'payment.record', 'backup.create', 'restore.drill']:
        expect(action in actions, f'missing audit action: {action}')
    print(f'PASS saas acceptance workflow {label}')


def main():
    run_acceptance('memory')
    run_isolation_acceptance('memory')
    run_account_boundary_acceptance('memory')
    run_storage_boundary_acceptance('memory')
    run_import_upload_acceptance('memory')
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        run_acceptance('persistent', db_url)
        run_isolation_acceptance('persistent', db_url)
        run_account_boundary_acceptance('persistent', db_url)
        run_storage_boundary_acceptance('persistent')
        run_import_upload_acceptance('persistent', db_url)


if __name__ == '__main__':
    main()
