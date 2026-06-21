#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Owner / room / charge target alignment for SaaS P0 migration."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def login_client(database_url=None, tenant='业主对齐物业', project='业主对齐项目', role='finance'):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': role,
        'role_code': role,
    })
    assert response.status_code == 200
    return client


def test_repository_persists_owner_and_binds_charge_target_with_tenant_scope():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        repo = create_saas_repository(db_url)
        tenant_a = repo.create_tenant('A物业')
        tenant_b = repo.create_tenant('B物业')
        project_a = repo.create_project(tenant_a['id'], 'A项目')
        project_b = repo.create_project(tenant_b['id'], 'B项目')
        owner_a = repo.create_owner(tenant_a['id'], project_a['id'], '张三', '13800000000', '住户')
        target_a = repo.create_charge_target(tenant_a['id'], project_a['id'], '1栋', '1单元', '101', '居民', 88, owner_a['id'])

        assert target_a['owner_id'] == owner_a['id']
        listed = repo.list_charge_targets(tenant_a['id'], project_a['id'])
        assert listed[0]['owner_name'] == '张三'
        assert listed[0]['owner_phone'] == '13800000000'
        assert repo.list_owners(tenant_a['id'], project_a['id'])[0]['name'] == '张三'
        assert repo.list_owners(tenant_b['id'], project_b['id']) == []
        try:
            repo.create_charge_target(tenant_b['id'], project_b['id'], '2栋', '1单元', '201', '居民', 90, owner_a['id'])
        except Exception as exc:
            assert 'owner' in str(exc).lower() or 'tenant' in str(exc).lower()
        else:
            raise AssertionError('cross-tenant owner binding was allowed')
        repo.close()


def test_api_creates_owner_and_charge_target_owner_binding_in_memory_and_persistent_modes():
    for db_url in [None, 'sqlite:///']:
        if db_url == 'sqlite:///':
            td = tempfile.TemporaryDirectory()
            actual_db_url = f"sqlite:///{Path(td.name) / 'saas.sqlite3'}"
        else:
            td = None
            actual_db_url = None
        try:
            client = login_client(actual_db_url)
            owner = client.post('/api/owners', json={'name': '李四', 'phone': '13900000000', 'owner_type': '业主'})
            assert owner.status_code == 200, owner.text
            owner_id = owner.json()['item']['id']
            target = client.post('/api/charge-targets', json={
                'building': '2栋', 'unit': '2单元', 'room_number': '202', 'category': '居民', 'area': 92, 'owner_id': owner_id,
            })
            assert target.status_code == 200, target.text
            assert target.json()['item']['owner_id'] == owner_id
            targets = client.get('/api/charge-targets').json()['items']
            assert targets[0]['owner_name'] == '李四'
            owners = client.get('/api/owners').json()['items']
            assert owners[0]['phone'] == '13900000000'
        finally:
            if td:
                td.cleanup()


def test_backoffice_charge_target_page_shows_owner_fields_and_owner_list():
    client = login_client()
    created = client.post('/backoffice/owners/create', data={'name': '王五', 'phone': '13700000000', 'owner_type': '业主'}, follow_redirects=False)
    assert created.status_code == 303
    page = client.get('/backoffice/charge-targets')
    assert page.status_code == 200
    for text in ['业主', '联系电话', '王五', '绑定业主', '房间/铺位与业主']:
        assert text in page.text
    owner_id = client.get('/api/owners').json()['items'][0]['id']
    target = client.post('/backoffice/charge-targets/create', data={
        'building': '3栋', 'unit': '1单元', 'room_number': '301', 'category': '居民', 'area': '100', 'owner_id': str(owner_id)
    }, follow_redirects=False)
    assert target.status_code == 303
    listed = client.get('/backoffice/charge-targets')
    assert '王五' in listed.text
    assert '3栋' in listed.text


def test_repository_persists_room_like_charge_target_fields_with_tenant_scope():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        repo = create_saas_repository(db_url)
        tenant = repo.create_tenant('字段物业')
        project = repo.create_project(tenant['id'], '字段项目')
        target = repo.create_charge_target(
            tenant['id'], project['id'], '商场', '一层', 'A-101', '商户', 66.5,
            floor=1, shop_name='云端便利店', tenant_name='王租户', tenant_phone='13600000000',
            payment_cycle='quarterly', notes='靠近东门', unit_price_override=8.5,
        )

        assert target['floor'] == 1
        assert target['shop_name'] == '云端便利店'
        listed = repo.list_charge_targets(tenant['id'], project['id'])
        assert listed[0]['tenant_name'] == '王租户'
        assert listed[0]['tenant_phone'] == '13600000000'
        assert listed[0]['payment_cycle'] == 'quarterly'
        assert listed[0]['notes'] == '靠近东门'
        repo.close()


def test_api_and_page_accept_room_like_charge_target_fields():
    client = login_client()
    target = client.post('/api/charge-targets', json={
        'building': '商业区', 'unit': '二层', 'room_number': 'B-201', 'category': '商户', 'area': 45,
        'floor': 2, 'shop_name': '云端咖啡', 'tenant_name': '赵承租', 'tenant_phone': '13500000000',
        'payment_cycle': 'monthly', 'notes': '测试备注', 'unit_price_override': 6,
    })
    assert target.status_code == 200, target.text
    item = target.json()['item']
    assert item['shop_name'] == '云端咖啡'
    assert item['tenant_name'] == '赵承租'
    assert item['payment_cycle'] == 'monthly'

    page = client.get('/backoffice/charge-targets')
    assert page.status_code == 200
    for text in ['楼层', '店名', '承租人', '承租电话', '缴费周期', '备注', '云端咖啡', '赵承租']:
        assert text in page.text

    created = client.post('/backoffice/charge-targets/create', data={
        'building': '商业区', 'unit': '三层', 'room_number': 'C-301', 'category': '商户', 'area': '55',
        'floor': '3', 'shop_name': '云端书店', 'tenant_name': '钱承租', 'tenant_phone': '13400000000',
        'payment_cycle': 'quarterly', 'notes': '页面创建', 'unit_price_override': '7',
    }, follow_redirects=False)
    assert created.status_code == 303
    listed = client.get('/backoffice/charge-targets')
    assert '云端书店' in listed.text
    assert '钱承租' in listed.text

def test_charge_target_page_mentions_chinese_payment_cycle_aliases():
    client = TestClient(create_app())
    client.post('/api/auth/login', json={
        'tenant_name': '周期提示物业', 'project_name': '周期提示项目', 'username': 'finance', 'role_code': 'finance'
    })

    page = client.get('/backoffice/charge-targets')

    assert page.status_code == 200
    for text in ['月付', '季付', '半年付', '年付']:
        assert text in page.text

