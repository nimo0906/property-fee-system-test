#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 import duplicate handling for SaaS commercial onboarding."""

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_service import SaasBackofficeService


def test_service_confirm_import_skips_existing_charge_target_in_same_project():
    service = SaasBackofficeService.in_memory()
    tenant = service.create_tenant('导入物业')
    project = service.create_project(tenant, '导入项目')
    user = service.create_user(tenant, 'finance', 'finance')
    service.create_charge_target(user, project, '1栋', '1单元', '101', '居民', 80)
    preview = service.preview_charge_target_import(user, project, [
        {'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '90'},
        {'building': '1栋', 'unit': '1单元', 'room_number': '102', 'category': '居民', 'area': '70'},
    ])

    result = service.confirm_charge_target_import(user, project, preview['import_id'])
    targets = service.list_charge_targets(user, project)

    assert result['created_count'] == 1
    assert result['duplicate_skipped_count'] == 1
    assert result['skipped_count'] == 1
    assert len(targets) == 2
    assert sorted(t['room_number'] for t in targets) == ['101', '102']


def test_api_import_duplicate_skip_is_tenant_scoped_and_does_not_skip_other_tenant():
    app = create_app()
    client_a = TestClient(app)
    client_b = TestClient(app)
    client_a.post('/api/auth/login', json={'tenant_name': 'A物业', 'project_name': 'A项目', 'username': 'finance_a', 'role_code': 'finance'})
    client_b.post('/api/auth/login', json={'tenant_name': 'B物业', 'project_name': 'B项目', 'username': 'finance_b', 'role_code': 'finance'})
    client_b.post('/api/charge-targets', json={'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 88})

    preview = client_a.post('/api/imports/charge-targets/preview', json={'rows': [
        {'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': '80'},
    ]})
    result = client_a.post('/api/imports/charge-targets/confirm', json={'import_id': preview.json()['import_id']})

    assert result.status_code == 200, result.text
    assert result.json()['created_count'] == 1
    assert result.json()['duplicate_skipped_count'] == 0
    assert len(client_a.get('/api/charge-targets').json()['items']) == 1
    assert len(client_b.get('/api/charge-targets').json()['items']) == 1


def test_backoffice_confirm_import_reports_duplicate_skip_count():
    client = TestClient(create_app())
    client.post('/api/auth/login', json={'tenant_name': '页面导入物业', 'project_name': '页面项目', 'username': 'finance', 'role_code': 'finance'})
    client.post('/api/charge-targets', json={'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80})
    csv_text = 'building,unit,room_number,category,area\n1栋,1单元,101,居民,80\n1栋,1单元,102,居民,70\n'
    page = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': csv_text})
    marker = 'name="import_id" value="'
    start = page.text.index(marker) + len(marker)
    import_id = int(page.text[start:page.text.index('"', start)])

    confirm = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})

    assert confirm.status_code == 200
    assert '成功导入：1' in confirm.text
    assert '重复跳过：1' in confirm.text
    assert len(client.get('/api/charge-targets').json()['items']) == 2


def test_backoffice_preview_marks_existing_charge_target_duplicates_before_confirm():
    client = TestClient(create_app())
    client.post('/api/auth/login', json={'tenant_name': '预览重复物业', 'project_name': '预览重复项目', 'username': 'finance', 'role_code': 'finance'})
    client.post('/api/charge-targets', json={'building': '1栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80})
    csv_text = 'building,unit,room_number,category,area\n1栋,1单元,101,居民,80\n1栋,1单元,102,居民,70\n'

    preview = client.post('/backoffice/imports/charge-targets/preview', data={'csv_text': csv_text})

    assert preview.status_code == 200
    assert '重复 1 行' in preview.text
    assert '已存在收费对象' in preview.text
    assert '1栋 1单元 101' in preview.text
    assert len(client.get('/api/charge-targets').json()['items']) == 1
