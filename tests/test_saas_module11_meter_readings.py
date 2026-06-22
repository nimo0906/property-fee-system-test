#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 11 cloud meter reading gate tests."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository

ROOT = Path(__file__).resolve().parents[1]


def _login(client, role_code='finance', tenant='水电物业', project='水电项目'):
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': f'{role_code}_user',
        'role_code': role_code,
    })
    assert response.status_code == 200, response.text


def test_module11_gate_script_exists_and_is_registered():
    script = ROOT / 'scripts/saas_module11_meter_reading_gate.py'
    assert script.exists(), 'missing module 11 meter reading gate script'
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_module11_meter_reading_gate.py' in gate


def test_module11_gate_documents_meter_scope():
    text = (ROOT / 'scripts/saas_module11_meter_reading_gate.py').read_text(encoding='utf-8')
    for keyword in [
        'module 11 meter reading',
        'tenant/project isolation',
        'previous/current/consumption',
        'confirmed reading to pending review bill',
        'water/electric fee mode',
        'release gate registration',
    ]:
        assert keyword in text


def test_repository_meter_reading_confirm_generates_meter_bill_and_audit():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('水电物业')
        project = repo.create_project(tenant['id'], '水电项目')
        other_tenant = repo.create_tenant('其他物业')
        other_project = repo.create_project(other_tenant['id'], '其他项目')
        actor = repo.create_user(tenant['id'], 'finance', 'finance')
        target = repo.create_charge_target(tenant['id'], project['id'], '商场', '一层', 'M-101', '商户', 40, shop_name='水电店')
        other_target = repo.create_charge_target(other_tenant['id'], other_project['id'], '商场', '一层', 'O-101', '商户', 99)
        water = repo.create_fee_type(tenant['id'], project['id'], '水费(商业)', 5.8, 'meter')
        other_fee = repo.create_fee_type(other_tenant['id'], other_project['id'], '水费(商业)', 5.8, 'meter')

        reading = repo.create_meter_reading(
            tenant['id'], project['id'], target['id'], water['id'], '2028-05', 12.5, 32.5,
            '2028-05-31', status='draft', actor_user_id=actor['id'], notes='五月水表'
        )
        assert reading['consumption'] == 20.0
        assert reading['status'] == 'draft'

        confirmed = repo.confirm_meter_reading(tenant['id'], project['id'], reading['id'], actor_user_id=actor['id'])
        assert confirmed['status'] == 'confirmed'
        assert confirmed['bill']['amount'] == 116.0
        assert confirmed['bill']['status'] == 'pending_review'
        assert confirmed['bill']['billing_period'] == '2028-05'
        assert repo.list_bills(tenant['id'], project['id'], '2028-05')[0]['amount'] == 116.0
        assert repo.list_bills(other_tenant['id'], other_project['id'], '2028-05') == []
        assert repo.list_meter_readings(other_tenant['id'], other_project['id']) == []
        assert repo.create_meter_reading(other_tenant['id'], other_project['id'], other_target['id'], other_fee['id'], '2028-05', 1, 2, '2028-05-31')['consumption'] == 1.0
        actions = [row['action'] for row in repo.list_audit_logs(tenant['id'], project['id'])]
        assert 'meter.create' in actions
        assert 'meter.confirm' in actions
        repo.close()


def test_api_meter_reading_prevents_lower_current_and_lists_only_current_project():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = TestClient(create_app(database_url=db_url))
        _login(client)
        target = client.post('/api/charge-targets', json={'building': '商场', 'unit': '一层', 'room_number': 'M-201', 'category': '商户', 'area': 30}).json()['item']
        fee = client.post('/api/fee-types', json={'name': '电费(商业)', 'unit_price': 0.85, 'billing_mode': 'meter'}).json()['item']

        ok = client.post('/api/meter-readings', json={
            'charge_target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-06',
            'previous_reading': 100, 'current_reading': 180, 'reading_date': '2028-06-30', 'status': 'confirmed',
        })
        assert ok.status_code == 200, ok.text
        assert ok.json()['item']['consumption'] == 80.0
        assert ok.json()['item']['bill']['amount'] == 68.0

        bad = client.post('/api/meter-readings', json={
            'charge_target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-07',
            'previous_reading': 200, 'current_reading': 199, 'reading_date': '2028-07-31', 'status': 'draft',
        })
        assert bad.status_code == 400
        assert 'current reading cannot be lower than previous reading' in bad.text

        other = TestClient(create_app(database_url=db_url))
        _login(other, tenant='其他水电物业', project='其他水电项目')
        assert other.get('/api/meter-readings').json()['items'] == []
        assert len(client.get('/api/meter-readings').json()['items']) == 1


def test_backoffice_meter_page_flow_and_no_secret_leakage():
    with tempfile.TemporaryDirectory() as td:
        client = TestClient(create_app(database_url=f"sqlite:///{Path(td) / 'saas.sqlite3'}"))
        _login(client)
        target = client.post('/api/charge-targets', json={
            'building': '商场A区', 'unit': '二层', 'room_number': 'E-201', 'category': '商户',
            'area': 50, 'shop_name': '水电样板店', 'tenant_name': '王商户',
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': '水费(商业)', 'unit_price': 5.8, 'billing_mode': 'meter'}).json()['item']

        page = client.get('/backoffice/meter-readings')
        assert page.status_code == 200
        for text in ['水电表抄表', '统一抄表台账', '抄表对象', '上次读数', '本次读数', '用量', '确认后生成待审核账单', '水费(商业)', 'E-201', '水电样板店']:
            assert text in page.text
        for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD', '.env']:
            assert hidden not in page.text

        submit = client.post('/backoffice/meter-readings/create', data={
            'charge_target_id': str(target['id']), 'fee_type_id': str(fee['id']), 'billing_period': '2028-08',
            'previous_reading': '10', 'current_reading': '30', 'reading_date': '2028-08-31', 'status': 'confirmed',
            'notes': '八月水表',
        }, follow_redirects=False)
        assert submit.status_code == 303
        result_page = client.get(submit.headers['location'])
        assert result_page.status_code == 200
        for text in ['抄表已保存', '2028-08', '20.0', '116.0', 'pending_review']:
            assert text in result_page.text


def test_meter_reading_roles_frontdesk_can_create_executive_readonly():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        setup = TestClient(create_app(database_url=db_url))
        _login(setup, role_code='finance')
        target = setup.post('/api/charge-targets', json={'building': '角色区', 'unit': '一层', 'room_number': 'R-101', 'category': '商户', 'area': 20}).json()['item']
        fee = setup.post('/api/fee-types', json={'name': '电费(商业)', 'unit_price': 1, 'billing_mode': 'meter'}).json()['item']

        frontdesk = TestClient(create_app(database_url=db_url))
        _login(frontdesk, role_code='frontdesk')
        created = frontdesk.post('/api/meter-readings', json={
            'charge_target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-09',
            'previous_reading': 0, 'current_reading': 10, 'reading_date': '2028-09-30', 'status': 'draft',
        })
        assert created.status_code == 200, created.text

        executive = TestClient(create_app(database_url=db_url))
        _login(executive, role_code='executive')
        assert executive.get('/backoffice/meter-readings').status_code == 200
        denied = executive.post('/api/meter-readings', json={
            'charge_target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2028-09',
            'previous_reading': 10, 'current_reading': 20, 'reading_date': '2028-09-30', 'status': 'draft',
        })
        assert denied.status_code == 403
