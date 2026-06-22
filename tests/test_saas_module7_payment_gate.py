#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 7 payment, arrears and ledger gate tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]


def _login(client):
    response = client.post('/api/auth/login', json={
        'tenant_name': '模块七物业',
        'project_name': '模块七项目',
        'username': 'finance',
        'role_code': 'finance',
    })
    assert response.status_code == 200


def test_module7_gate_script_exists_and_is_registered():
    script = ROOT / 'scripts/saas_module7_payment_arrears_gate.py'
    assert script.exists(), 'missing module 7 payment arrears gate script'
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_module7_payment_arrears_gate.py' in gate


def test_module7_gate_script_documents_payment_arrears_idempotency_ledger_scope():
    text = (ROOT / 'scripts/saas_module7_payment_arrears_gate.py').read_text(encoding='utf-8')
    for keyword in [
        'partial payment',
        'arrears linkage',
        'idempotency conflict',
        'payment ledger',
        'tenant isolation',
        'release gate registration',
    ]:
        assert keyword in text


def test_memory_payment_api_rejects_unknown_bill_without_500():
    client = TestClient(create_app())
    _login(client)

    response = client.post('/api/payments', json={
        'bill_id': 99999,
        'amount': 1,
        'method': 'cash',
        'idempotency_key': 'MODULE7-MISSING-BILL',
    })

    assert response.status_code in {400, 403}
    assert response.status_code != 500
    assert 'Traceback' not in response.text


def test_memory_payment_page_rejects_unknown_bill_without_500():
    client = TestClient(create_app())
    _login(client)

    response = client.post('/backoffice/payments/create', data={
        'bill_id': '99999',
        'amount': '1',
        'method': 'cash',
        'idempotency_key': 'MODULE7-PAGE-MISSING-BILL',
    }, follow_redirects=False)

    assert response.status_code in {400, 403}
    assert response.status_code != 500
    assert 'Traceback' not in response.text
