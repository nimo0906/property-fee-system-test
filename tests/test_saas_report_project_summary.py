#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS report project summary tests."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def _client(database_url, tenant='项目汇总物业', project='一期', username='admin'):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': username,
        'role_code': 'system_admin',
    })
    assert response.status_code == 200
    return client


def _seed_bill(client, period, room, area, paid):
    target = client.post('/api/charge-targets', json={
        'building': '项目楼', 'unit': '1单元', 'room_number': room, 'category': '居民', 'area': area,
    }).json()['item']
    fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2}).json()['item']
    bill = client.post('/api/bills/generate', json={
        'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': period,
        'service_start': f'{period}-01', 'service_end': f'{period}-28',
    }).json()['item']
    client.post(f"/api/bills/{bill['id']}/approve", json={})
    if paid:
        response = client.post('/api/payments', json={
            'bill_id': bill['id'], 'amount': paid, 'method': 'cash',
            'idempotency_key': f'PROJECT-SUMMARY-{room}-{period}',
        })
        assert response.status_code == 200
    return bill


def test_report_page_and_csv_show_project_summary_for_current_tenant_only():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = _client(db_url)
        created = client.post('/backoffice/tenant-projects/create', data={'name': '二期', 'code': 'P2'}, follow_redirects=False)
        assert created.status_code == 303
        repo = create_saas_repository(db_url)
        projects = {row['name']: row for row in repo.list_projects()}
        repo.close()

        _seed_bill(client, '2028-05', '101', 100, 50)
        switched = client.post('/api/auth/switch-project', json={'project_id': projects['二期']['id']})
        assert switched.status_code == 200
        _seed_bill(client, '2028-05', '201', 200, 400)

        client_b = _client(db_url, tenant='其他项目汇总物业', project='其他项目', username='other-admin')
        _seed_bill(client_b, '2028-05', '999', 999, 0)

        page = client.get('/backoffice/reports?period=2028-05')
        assert page.status_code == 200
        for text in ['按项目汇总', '一期', '二期', '200.0', '50.0', '150.0', '400.0', '400.0', '0.0', '25.00%', '100.00%']:
            assert text in page.text
        assert '其他项目' not in page.text
        assert '/api/exports/reports/projects.csv?period=2028-05' in page.text

        api = client.get('/api/reports/projects?period=2028-05')
        assert api.status_code == 200
        assert api.json()['items'] == [
            {'name': '一期', 'bill_count': 1, 'bill_amount_total': 200.0, 'payment_amount_total': 50.0, 'unpaid_amount_total': 150.0, 'collection_rate': '25.00%', 'arrears_rate': '75.00%'},
            {'name': '二期', 'bill_count': 1, 'bill_amount_total': 400.0, 'payment_amount_total': 400.0, 'unpaid_amount_total': 0.0, 'collection_rate': '100.00%', 'arrears_rate': '0.00%'},
        ]

        exported = client.get('/api/exports/reports/projects.csv?period=2028-05')
        assert exported.status_code == 200
        content = exported.json()['content']
        assert exported.json()['filename'] == 'report-projects-2028-05.csv'
        assert 'name,bill_count,bill_amount_total,payment_amount_total,unpaid_amount_total,collection_rate,arrears_rate' in content
        assert '一期,1,200.0,50.0,150.0,25.00%,75.00%' in content
        assert '二期,1,400.0,400.0,0.0,100.00%,0.00%' in content
        assert '其他项目' not in content
        for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
            assert hidden not in content
