#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 9 reports, exports, receipts and print gate tests."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]


def _login(client, tenant='模块九物业', project='模块九项目', role_code='finance'):
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': f'{role_code}_user',
        'role_code': role_code,
    })
    assert response.status_code == 200


def _seed_paid_bill(client, period='2029-09', room='R-901', amount=300, paid=120):
    target = client.post('/api/charge-targets', json={
        'building': '报表楼', 'unit': '九层', 'room_number': room,
        'category': '商户', 'area': amount, 'shop_name': f'{room}店',
        'tenant_name': f'{room}承租人',
    }).json()['item']
    fee = client.post('/api/fee-types', json={
        'name': '模块九物业费', 'unit_price': 1, 'billing_mode': 'area',
    }).json()['item']
    bill = client.post('/api/bills/generate', json={
        'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': period,
        'service_start': f'{period}-01', 'service_end': f'{period}-28',
    }).json()['item']
    client.post(f"/api/bills/{bill['id']}/approve", json={})
    payment = client.post('/api/payments', json={
        'bill_id': bill['id'], 'amount': paid, 'method': 'cash',
        'idempotency_key': f'MODULE9-{period}-{room}',
    }).json()['item']
    return bill, payment


def test_module9_gate_script_exists_and_is_registered():
    script = ROOT / 'scripts/saas_module9_report_export_print_gate.py'
    assert script.exists(), 'missing module 9 report/export/print gate script'
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_module9_report_export_print_gate.py' in gate


def test_module9_gate_documents_delivery_required_report_export_receipt_print_scope():
    text = (ROOT / 'scripts/saas_module9_report_export_print_gate.py').read_text(encoding='utf-8')
    for keyword in [
        'report summary',
        'CSV exports',
        'receipt detail',
        'print pages',
        'tenant isolation',
        'release gate registration',
    ]:
        assert keyword in text


def test_report_print_page_is_formal_printable_and_tenant_scoped():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client_a = TestClient(create_app(database_url=db_url))
        _login(client_a, tenant='模块九A物业', project='模块九A项目')
        _seed_paid_bill(client_a)

        page = client_a.get('/backoffice/reports/print?period=2029-09')

        assert page.status_code == 200
        for text in [
            '报表打印', '正式对账报表', 'window.print()', '@media print',
            '模块九A物业', '模块九A项目', '2029-09', '应收', '实收', '欠费',
            '300.0', '120.0', '180.0', '收缴率', '40.00%', '欠费率', '60.00%',
            '按项目汇总', '按楼栋 / 区域汇总', '欠费账单明细', 'R-901店',
        ]:
            assert text in page.text
        for hidden in ['tenant_id', 'project_id', 'idempotency_key', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
            assert hidden not in page.text

        client_b = TestClient(create_app(database_url=db_url))
        _login(client_b, tenant='模块九B物业', project='模块九B项目')
        page_b = client_b.get('/backoffice/reports/print?period=2029-09')
        assert page_b.status_code == 200
        assert 'R-901店' not in page_b.text
        assert '300.0' not in page_b.text


def test_report_workbench_links_print_page_with_current_period():
    with tempfile.TemporaryDirectory() as td:
        client = TestClient(create_app(database_url=f"sqlite:///{Path(td) / 'saas.sqlite3'}"))
        _login(client)
        _seed_paid_bill(client, period='2029-10')

        page = client.get('/backoffice/reports?period=2029-10')

        assert page.status_code == 200
        assert '/backoffice/reports/print?period=2029-10' in page.text
        assert '打印报表' in page.text
