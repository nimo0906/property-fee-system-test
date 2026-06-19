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
