#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import mapping from legacy rooms/owners fields into SaaS owners + charge targets."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_service import SaasBackofficeService


def test_in_memory_import_maps_legacy_owner_room_fields_without_preview_writes():
    service = SaasBackofficeService.in_memory()
    tenant = service.create_tenant('导入物业')
    project = service.create_project(tenant, '导入项目')
    user = service.create_user(tenant, 'finance', 'finance')
    preview = service.preview_charge_target_import(user, project, [
        {'owner_name': '张三', 'owner_phone': '13800000000', 'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '80'},
        {'业主姓名': '李四', '联系电话': '13900000000', '楼栋/区域': '商业街', '单元/分区': 'A区', '房号/铺位号': 'A-01', '类型': '商户', '面积': '120'},
    ])
    assert preview['valid_count'] == 2
    assert service.list_owners(user, project) == []
    assert service.list_charge_targets(user, project) == []
    review = service.get_import_review(user, project, preview['import_id'])
    assert review['valid_rows'][0]['owner_name'] == '张三'
    assert review['valid_rows'][1]['owner_name'] == '李四'
    result = service.confirm_charge_target_import(user, project, preview['import_id'])
    assert result == {'created_count': 2, 'skipped_count': 0, 'owner_created_count': 2}
    owners = service.list_owners(user, project)
    targets = service.list_charge_targets(user, project)
    assert [o['name'] for o in owners] == ['张三', '李四']
    assert targets[0]['owner_name'] == '张三'
    assert targets[1]['owner_phone'] == '13900000000'


def test_api_import_mapping_persistent_mode_creates_owner_and_bound_target():
    with tempfile.TemporaryDirectory() as td:
        client = TestClient(create_app(database_url=f"sqlite:///{Path(td) / 'saas.sqlite3'}"))
        client.post('/api/auth/login', json={'tenant_name': '持久导入物业', 'project_name': '持久导入项目', 'username': 'finance', 'role_code': 'finance'})
        preview = client.post('/api/imports/charge-targets/preview', json={'rows': [
            {'owner_name': '王五', 'owner_phone': '13700000000', 'building': '2栋', 'unit': '2单元', 'room_number': '202', 'category': '居民', 'area': '92'},
        ]})
        assert preview.status_code == 200, preview.text
        assert client.get('/api/owners').json()['items'] == []
        confirmed = client.post('/api/imports/charge-targets/confirm', json={'import_id': preview.json()['import_id']})
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()['owner_created_count'] == 1
        owners = client.get('/api/owners').json()['items']
        targets = client.get('/api/charge-targets').json()['items']
        assert owners[0]['name'] == '王五'
        assert targets[0]['owner_id'] == owners[0]['id']
        assert targets[0]['owner_name'] == '王五'


def test_import_template_mentions_owner_mapping_fields():
    client = TestClient(create_app())
    client.post('/api/auth/login', json={'tenant_name': '模板物业', 'project_name': '模板项目', 'username': 'finance', 'role_code': 'finance'})
    csv = client.get('/api/imports/templates/charge-targets.csv')
    assert csv.status_code == 200
    for text in ['owner_name', 'owner_phone', '楼栋/区域', '房号/铺位号']:
        assert text in csv.text


def test_import_maps_room_like_fields_and_keeps_preview_side_effect_free():
    service = SaasBackofficeService.in_memory()
    tenant = service.create_tenant('字段导入物业')
    project = service.create_project(tenant, '字段导入项目')
    user = service.create_user(tenant, 'finance', 'finance')

    preview = service.preview_charge_target_import(user, project, [{
        '楼栋/区域': '商场', '单元/分区': '一层', '房号/铺位号': 'A-108', '类型': '商户', '面积': '33.5',
        '楼层': '1', '店名': '导入花店', '承租人': '孙承租', '承租人电话': '13300000000',
        '缴费周期': '季付', '备注': '导入备注', '独立单价': '9.5', '业主姓名': '孙业主',
    }])

    assert preview['valid_count'] == 1
    assert service.list_charge_targets(user, project) == []
    review = service.get_import_review(user, project, preview['import_id'])
    row = review['valid_rows'][0]
    assert row['floor'] == 1
    assert row['shop_name'] == '导入花店'
    assert row['tenant_name'] == '孙承租'
    assert row['tenant_phone'] == '13300000000'
    assert row['payment_cycle'] == 'quarterly'
    assert row['notes'] == '导入备注'

    result = service.confirm_charge_target_import(user, project, preview['import_id'])
    assert result['created_count'] == 1
    target = service.list_charge_targets(user, project)[0]
    assert target['shop_name'] == '导入花店'
    assert target['payment_cycle'] == 'quarterly'
    assert target['notes'] == '导入备注'


def test_import_rejects_invalid_floor_without_polluting_valid_rows():
    service = SaasBackofficeService.in_memory()
    tenant = service.create_tenant('错误导入物业')
    project = service.create_project(tenant, '错误导入项目')
    user = service.create_user(tenant, 'finance', 'finance')

    preview = service.preview_charge_target_import(user, project, [
        {'楼栋/区域': '1栋', '房号/铺位号': '101', '面积': '80', '楼层': 'not-a-number'},
        {'楼栋/区域': '1栋', '房号/铺位号': '102', '面积': '90', '楼层': '2'},
    ])

    assert preview['valid_count'] == 1
    assert preview['error_count'] == 1
    result = service.confirm_charge_target_import(user, project, preview['import_id'])
    assert result['created_count'] == 1
    targets = service.list_charge_targets(user, project)
    assert targets[0]['room_number'] == '102'
    assert targets[0]['floor'] == 2


def test_import_maps_desktop_basic_template_fields_without_preview_writes():
    service = SaasBackofficeService.in_memory()
    tenant = service.create_tenant('基础模板物业')
    project = service.create_project(tenant, '基础模板项目')
    user = service.create_user(tenant, 'finance', 'finance')

    preview = service.preview_charge_target_import(user, project, [{
        '项目': '默认项目', '楼栋/区域': '商业区', '单元/分区': '一层', '房号/铺位号': 'SP-101',
        '楼层': '1', '对象类型': '商户', '面积㎡': '88.5', '物业费单价': '4.8', '水费标准': '非居民',
        '业主姓名': '甲商贸', '业主电话': '13900000000', '身份证号': 'ID-OWNER',
        '租户姓名': '李四', '租户电话': '13800000001', '租户身份证号': 'ID-TENANT',
        '合同开始日期': '2026-01-01', '合同结束日期': '2026-12-31', '缴费周期': '季付',
        '店铺名称': '某某便利店', '业态/商户类别': '餐饮', '备注': '基础资料模板',
    }])

    assert preview['valid_count'] == 1
    assert service.list_owners(user, project) == []
    assert service.list_charge_targets(user, project) == []
    row = service.get_import_review(user, project, preview['import_id'])['valid_rows'][0]
    assert row['building'] == '商业区'
    assert row['unit'] == '一层'
    assert row['room_number'] == 'SP-101'
    assert row['floor'] == 1
    assert row['category'] == '商户'
    assert row['area'] == 88.5
    assert row['unit_price_override'] == 4.8
    assert row['owner_name'] == '甲商贸'
    assert row['owner_phone'] == '13900000000'
    assert row['tenant_name'] == '李四'
    assert row['tenant_phone'] == '13800000001'
    assert row['payment_cycle'] == 'quarterly'
    assert row['shop_name'] == '某某便利店'
    assert row['notes'] == '基础资料模板'

    result = service.confirm_charge_target_import(user, project, preview['import_id'])
    assert result['created_count'] == 1
    target = service.list_charge_targets(user, project)[0]
    assert target['room_number'] == 'SP-101'
    assert target['unit_price_override'] == 4.8
    assert target['payment_cycle'] == 'quarterly'
