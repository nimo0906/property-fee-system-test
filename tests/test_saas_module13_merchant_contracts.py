#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 13 cloud merchant contract and amendment tests."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository

ROOT = Path(__file__).resolve().parents[1]


def _login(client, role_code='finance', tenant='合同物业', project='合同项目'):
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': f'{role_code}_user',
        'role_code': role_code,
    })
    assert response.status_code == 200, response.text


def test_module13_gate_script_exists_and_is_registered():
    script = ROOT / 'scripts/saas_module13_merchant_contract_gate.py'
    assert script.exists(), 'missing module 13 merchant contract gate script'
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_module13_merchant_contract_gate.py' in gate


def test_module13_gate_documents_contract_scope():
    text = (ROOT / 'scripts/saas_module13_merchant_contract_gate.py').read_text(encoding='utf-8')
    for keyword in [
        'module 13 merchant contract',
        'tenant/project isolation',
        'contract period rent property fee deposit',
        'contract amendment effective date',
        'confirmed amendment recalculates future bills',
        'release gate registration',
    ]:
        assert keyword in text


def test_repository_contract_amendment_recalculates_future_bills_and_isolates_tenants():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('合同物业')
        project = repo.create_project(tenant['id'], '合同项目')
        other_tenant = repo.create_tenant('其他合同物业')
        other_project = repo.create_project(other_tenant['id'], '其他合同项目')
        actor = repo.create_user(tenant['id'], 'finance', 'finance')
        target = repo.create_charge_target(tenant['id'], project['id'], '商场A区', '一层', 'A-101', '商户', 50, shop_name='合同店', tenant_name='张商户')
        other_target = repo.create_charge_target(other_tenant['id'], other_project['id'], '商场B区', '二层', 'B-201', '商户', 80)

        contract = repo.create_merchant_contract(
            tenant['id'], project['id'], target['id'], 'MC-2028-001', '张商户', '合同店',
            '2028-01-01', '2028-12-31', 50, 100, 8, 'monthly', 'quarterly', 10000,
            'active', actor_user_id=actor['id'], notes='年度合同'
        )
        assert contract['monthly_rent_amount'] == 5000.0
        assert contract['monthly_property_fee_amount'] == 400.0
        assert contract['deposit_amount'] == 10000.0

        bill_jan = repo.generate_contract_bill(tenant['id'], project['id'], contract['id'], '2028-01', '2028-01-01', '2028-01-31', actor_user_id=actor['id'])
        assert bill_jan['amount'] == 5400.0
        assert bill_jan['status'] == 'pending_review'
        amendment = repo.create_contract_amendment(
            tenant['id'], project['id'], contract['id'], 'AM-001', '2028-04-01',
            rent_unit_price=120, property_rate=9, actor_user_id=actor['id'], notes='四月调价'
        )
        assert amendment['status'] == 'confirmed'
        bill_apr = repo.generate_contract_bill(tenant['id'], project['id'], contract['id'], '2028-04', '2028-04-01', '2028-04-30', actor_user_id=actor['id'])
        assert bill_apr['amount'] == 6450.0
        assert bill_apr['contract_id'] == contract['id']
        assert repo.list_merchant_contracts(other_tenant['id'], other_project['id']) == []
        other_contract = repo.create_merchant_contract(other_tenant['id'], other_project['id'], other_target['id'], 'OC-1', '其他商户', '隔离店', '2028-01-01', '2028-12-31', 80, 20, 2, 'monthly', 'monthly', 1000)
        assert len(repo.list_merchant_contracts(other_tenant['id'], other_project['id'])) == 1
        assert len(repo.list_merchant_contracts(tenant['id'], project['id'])) == 1
        actions = [row['action'] for row in repo.list_audit_logs(tenant['id'], project['id'])]
        assert 'merchant_contract.create' in actions
        assert 'merchant_contract.bill_generate' in actions
        assert 'contract_amendment.confirm' in actions
        repo.close()


def test_api_contract_prevents_cross_tenant_target_and_period_outside_contract():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = TestClient(create_app(database_url=db_url))
        _login(client)
        target = client.post('/api/charge-targets', json={'building': '商场A区', 'unit': '一层', 'room_number': 'C-101', 'category': '商户', 'area': 60, 'shop_name': 'API店', 'tenant_name': 'API商户'}).json()['item']
        contract_response = client.post('/api/merchant-contracts', json={
            'charge_target_id': target['id'], 'contract_no': 'API-001', 'merchant_name': 'API商户', 'shop_name': 'API店',
            'start_date': '2028-01-01', 'end_date': '2028-03-31', 'contract_area': 60,
            'rent_unit_price': 90, 'property_rate': 7, 'rent_cycle': 'monthly', 'property_cycle': 'monthly',
            'deposit_amount': 3000, 'status': 'active', 'notes': 'API合同',
        })
        assert contract_response.status_code == 200, contract_response.text
        contract = contract_response.json()['item']
        outside = client.post(f"/api/merchant-contracts/{contract['id']}/generate-bill", json={'billing_period': '2028-04', 'service_start': '2028-04-01', 'service_end': '2028-04-30'})
        assert outside.status_code == 400
        assert 'outside contract period' in outside.text

        other = TestClient(create_app(database_url=db_url))
        _login(other, tenant='其他合同物业', project='其他合同项目')
        denied = other.post('/api/merchant-contracts', json={
            'charge_target_id': target['id'], 'contract_no': 'BAD-001', 'merchant_name': '跨租户', 'shop_name': '跨租户',
            'start_date': '2028-01-01', 'end_date': '2028-12-31', 'contract_area': 60,
            'rent_unit_price': 1, 'property_rate': 1, 'rent_cycle': 'monthly', 'property_cycle': 'monthly', 'deposit_amount': 1,
        })
        assert denied.status_code == 403
        assert client.get('/api/merchant-contracts').json()['total'] == 1
        assert other.get('/api/merchant-contracts').json()['total'] == 0


def test_backoffice_contract_page_flow_and_no_secret_leakage():
    with tempfile.TemporaryDirectory() as td:
        client = TestClient(create_app(database_url=f"sqlite:///{Path(td) / 'saas.sqlite3'}"))
        _login(client)
        target = client.post('/api/charge-targets', json={
            'building': '商场A区', 'unit': '三层', 'room_number': 'K-301', 'category': '商户',
            'area': 45, 'shop_name': '页面合同店', 'tenant_name': '赵商户',
        }).json()['item']

        page = client.get('/backoffice/merchant-contracts')
        assert page.status_code == 200
        for text in ['商户合同', '合同变更', '合同周期', '租金单价', '物业费单价', '生成合同账单', 'K-301', '页面合同店']:
            assert text in page.text
        for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
            assert hidden not in page.text

        created = client.post('/backoffice/merchant-contracts/create', data={
            'charge_target_id': str(target['id']), 'contract_no': 'PAGE-001', 'merchant_name': '赵商户', 'shop_name': '页面合同店',
            'start_date': '2028-01-01', 'end_date': '2028-12-31', 'contract_area': '45',
            'rent_unit_price': '80', 'property_rate': '6', 'rent_cycle': 'monthly', 'property_cycle': 'monthly',
            'deposit_amount': '5000', 'status': 'active', 'notes': '页面新增',
        }, follow_redirects=False)
        assert created.status_code == 303
        contract_page = client.get(created.headers['location'])
        for text in ['合同已新增', 'PAGE-001', '赵商户', '页面合同店', '3600.0', '270.0']:
            assert text in contract_page.text
        contract_id = client.get('/api/merchant-contracts').json()['items'][0]['id']
        amend = client.post(f'/backoffice/merchant-contracts/{contract_id}/amend', data={
            'amendment_no': 'PAGE-AM-1', 'effective_date': '2028-05-01', 'rent_unit_price': '100',
            'property_rate': '7', 'notes': '五月调价',
        }, follow_redirects=False)
        assert amend.status_code == 303
        bill = client.post(f'/backoffice/merchant-contracts/{contract_id}/generate-bill', data={
            'billing_period': '2028-05', 'service_start': '2028-05-01', 'service_end': '2028-05-31',
        }, follow_redirects=False)
        assert bill.status_code == 303
        result = client.get(bill.headers['location'])
        for text in ['合同账单已生成', 'PAGE-AM-1', '2028-05', '4815.0', 'pending_review']:
            assert text in result.text


def test_contract_roles_finance_can_write_executive_readonly():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        setup = TestClient(create_app(database_url=db_url))
        _login(setup, role_code='finance')
        target = setup.post('/api/charge-targets', json={'building': '角色区', 'unit': '一层', 'room_number': 'R-201', 'category': '商户', 'area': 20}).json()['item']

        executive = TestClient(create_app(database_url=db_url))
        _login(executive, role_code='executive')
        assert executive.get('/backoffice/merchant-contracts').status_code == 200
        denied = executive.post('/api/merchant-contracts', json={
            'charge_target_id': target['id'], 'contract_no': 'ROLE-001', 'merchant_name': '只读', 'shop_name': '只读',
            'start_date': '2028-01-01', 'end_date': '2028-12-31', 'contract_area': 20,
            'rent_unit_price': 10, 'property_rate': 1, 'rent_cycle': 'monthly', 'property_cycle': 'monthly', 'deposit_amount': 100,
        })
        assert denied.status_code == 403
