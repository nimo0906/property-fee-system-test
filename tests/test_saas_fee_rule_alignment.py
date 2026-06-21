#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 fee rule alignment: area and fixed amount billing."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def login_client(database_url=None):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '规则物业', 'project_name': '规则项目', 'username': 'finance', 'role_code': 'finance'
    })
    assert response.status_code == 200
    return client


def test_repository_fee_type_supports_area_and_fixed_billing_modes():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('规则物业')
        project = repo.create_project(tenant['id'], '规则项目')
        target = repo.create_charge_target(tenant['id'], project['id'], '1栋', '1单元', '101', '居民', 80)
        area_fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 2.5, 'area')
        fixed_fee = repo.create_fee_type(tenant['id'], project['id'], '垃圾清运费', 30, 'fixed')
        assert area_fee['billing_mode'] == 'area'
        assert fixed_fee['billing_mode'] == 'fixed'
        area_bill = repo.create_bill(tenant['id'], project['id'], target['id'], area_fee['id'], '2026-09', '2026-09-01', '2026-09-30', None)
        fixed_bill = repo.create_bill(tenant['id'], project['id'], target['id'], fixed_fee['id'], '2026-09', '2026-09-01', '2026-09-30', None)
        assert area_bill['amount'] == 200.0
        assert fixed_bill['amount'] == 30.0
        listed = repo.list_fee_types(tenant['id'], project['id'])
        assert [row['billing_mode'] for row in listed] == ['area', 'fixed']
        repo.close()


def test_api_and_bill_generation_use_fixed_billing_mode_in_memory_and_persistent_modes():
    for database_url in [None, 'persistent']:
        if database_url == 'persistent':
            td = tempfile.TemporaryDirectory()
            db_url = f"sqlite:///{Path(td.name) / 'saas.sqlite3'}"
        else:
            td = None
            db_url = None
        try:
            client = login_client(db_url)
            target = client.post('/api/charge-targets', json={'building': '2栋', 'unit': '1单元', 'room_number': '201', 'category': '居民', 'area': 90}).json()['item']
            fee = client.post('/api/fee-types', json={'name': '固定服务费', 'unit_price': 45, 'billing_mode': 'fixed'})
            assert fee.status_code == 200, fee.text
            assert fee.json()['item']['billing_mode'] == 'fixed'
            bill = client.post('/api/bills/generate', json={
                'target_id': target['id'], 'fee_type_id': fee.json()['item']['id'], 'billing_period': '2026-10',
                'service_start': '2026-10-01', 'service_end': '2026-10-31',
            })
            assert bill.status_code == 200, bill.text
            assert bill.json()['item']['amount'] == 45.0
        finally:
            if td:
                td.cleanup()


def test_fee_type_page_exposes_billing_mode_and_keeps_tenant_scoped_rules():
    with tempfile.TemporaryDirectory() as td:
        client = login_client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        response = client.post('/backoffice/fee-types/create', data={'name': '固定停车费', 'unit_price': '100', 'billing_mode': 'fixed'}, follow_redirects=False)
        assert response.status_code == 303
        page = client.get('/backoffice/fee-types')
        assert page.status_code == 200
        for text in ['计费方式', '按面积', '固定金额', '固定停车费']:
            assert text in page.text
        assert '固定金额' in page.text
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 fee rule alignment: target price override and service period proration."""

import tempfile
from pathlib import Path

from server.saas_repository import create_saas_repository


def test_repository_uses_target_price_override_before_fee_default_price():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('规则物业')
        project = repo.create_project(tenant['id'], '规则项目')
        target = repo.create_charge_target(
            tenant['id'], project['id'], '商场', '一层', 'A-101', '商户', 50, unit_price_override=8
        )
        fee = repo.create_fee_type(tenant['id'], project['id'], '商户物业费', 5, 'area')
        bill = repo.create_bill(
            tenant['id'], project['id'], target['id'], fee['id'], '2026-09', '2026-09-01', '2026-09-30', None
        )
        assert bill['amount'] == 400.0
        listed = repo.list_charge_targets(tenant['id'], project['id'])
        assert listed[0]['unit_price_override'] == 8.0
        repo.close()


def test_repository_prorates_amount_by_service_months_for_multi_month_period():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('规则物业')
        project = repo.create_project(tenant['id'], '规则项目')
        target = repo.create_charge_target(tenant['id'], project['id'], '1栋', '1单元', '101', '居民', 80)
        fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 2, 'area')
        bill = repo.create_bill(
            tenant['id'], project['id'], target['id'], fee['id'], '2026-09~2026-11', '2026-09-01', '2026-11-30', None
        )
        assert bill['amount'] == 480.0
        repo.close()



def test_repository_prorates_partial_month_service_period_by_days():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('按天规则物业')
        project = repo.create_project(tenant['id'], '按天规则项目')
        target = repo.create_charge_target(tenant['id'], project['id'], '1栋', '1单元', '101', '居民', 31)
        fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 1, 'area')

        bill = repo.create_bill(tenant['id'], project['id'], target['id'], fee['id'], '2026-01', '2026-01-16', '2026-01-31', None)

        assert bill['amount'] == 16.0
        repo.close()


def test_api_generates_partial_month_amount_by_service_days():
    client = login_client()
    target = client.post('/api/charge-targets', json={
        'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 31,
    }).json()['item']
    fee = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 1, 'billing_mode': 'area'}).json()['item']

    bill = client.post('/api/bills/generate', json={
        'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2026-01',
        'service_start': '2026-01-16', 'service_end': '2026-01-31',
    })

    assert bill.status_code == 200, bill.text
    assert bill.json()['item']['amount'] == 16.0


def test_fixed_billing_mode_prorates_partial_month_by_service_days():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('固定按天物业')
        project = repo.create_project(tenant['id'], '固定按天项目')
        target = repo.create_charge_target(tenant['id'], project['id'], '车场', '一区', 'P-001', '车位', 1)
        fee = repo.create_fee_type(tenant['id'], project['id'], '车位费', 310, 'fixed')

        bill = repo.create_bill(tenant['id'], project['id'], target['id'], fee['id'], '2026-01', '2026-01-16', '2026-01-31', None)

        assert bill['amount'] == 160.0
        repo.close()


def test_service_period_from_first_to_28th_keeps_legacy_full_month_amount():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('兼容规则物业')
        project = repo.create_project(tenant['id'], '兼容规则项目')
        target = repo.create_charge_target(tenant['id'], project['id'], '1栋', '1单元', '101', '居民', 100)
        fee = repo.create_fee_type(tenant['id'], project['id'], '物业费', 1, 'area')

        bill = repo.create_bill(tenant['id'], project['id'], target['id'], fee['id'], '2026-06', '2026-06-01', '2026-06-28', None)

        assert bill['amount'] == 100.0
        repo.close()

def test_api_and_page_accept_target_price_override_for_saas_billing():
    with tempfile.TemporaryDirectory() as td:
        client = login_client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        target = client.post('/api/charge-targets', json={
            'building': '商场', 'unit': '一层', 'room_number': 'B-101', 'category': '商户',
            'area': 60, 'unit_price_override': 7,
        }).json()['item']
        fee = client.post('/api/fee-types', json={'name': '商户物业费', 'unit_price': 3, 'billing_mode': 'area'}).json()['item']
        bill = client.post('/api/bills/generate', json={
            'target_id': target['id'], 'fee_type_id': fee['id'], 'billing_period': '2026-12',
            'service_start': '2026-12-01', 'service_end': '2026-12-31',
        })
        assert bill.status_code == 200, bill.text
        assert bill.json()['item']['amount'] == 420.0
        page = client.get('/backoffice/charge-targets')
        assert '独立单价' in page.text


def test_import_mapping_keeps_target_price_override_for_confirmed_rows():
    client = login_client()
    preview = client.post('/api/imports/charge-targets/preview', json={'rows': [{
        '业主姓名': '张商户', '楼栋/区域': '商场', '单元/分区': '二层', '房号/铺位号': 'C-201',
        '类型': '商户', '面积': '40', '独立单价': '9',
    }]})
    assert preview.status_code == 200, preview.text
    confirm = client.post('/api/imports/charge-targets/confirm', json={'import_id': preview.json()['import_id']})
    assert confirm.status_code == 200, confirm.text
    targets = client.get('/api/charge-targets').json()['items']
    assert targets[0]['unit_price_override'] == 9.0


def test_target_price_override_does_not_replace_fixed_amount_fee():
    with tempfile.TemporaryDirectory() as td:
        repo = create_saas_repository(f"sqlite:///{Path(td) / 'saas.sqlite3'}")
        tenant = repo.create_tenant('固定金额覆盖物业')
        project = repo.create_project(tenant['id'], '固定金额覆盖项目')
        target = repo.create_charge_target(
            tenant['id'], project['id'], '商场', '一层', 'P-001', '商户', 50, unit_price_override=8
        )
        fee = repo.create_fee_type(tenant['id'], project['id'], '固定停车费', 120, 'fixed')

        bill = repo.create_bill(
            tenant['id'], project['id'], target['id'], fee['id'], '2026-09', '2026-09-01', '2026-09-30', None
        )

        assert bill['amount'] == 120.0
        repo.close()
