#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Charge target Excel import preview tests for SaaS backoffice."""

import io
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def _client(database_url, tenant='Excel导入物业', project='Excel导入项目'):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': 'finance',
        'role_code': 'finance',
    })
    assert response.status_code == 200
    return client


def _xlsx_bytes(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = '收费对象'
    for row in rows:
        ws.append(row)
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def test_import_page_shows_excel_preview_upload_entry():
    with tempfile.TemporaryDirectory() as td:
        client = _client(f"sqlite:///{Path(td) / 'saas.sqlite3'}")

        page = client.get('/backoffice/imports')

        assert page.status_code == 200
        assert 'Excel 文件预览' in page.text
        assert 'name="xlsx_file"' in page.text
        assert 'enctype="multipart/form-data"' in page.text
        assert '/backoffice/imports/charge-targets/xlsx-preview' in page.text


def test_xlsx_preview_does_not_write_and_confirm_imports_only_valid_rows():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = _client(db_url)
        content = _xlsx_bytes([
            ['业主姓名', '联系电话', '楼栋/区域', '单元/分区', '房号/铺位号', '类型', '面积', '店名', '缴费周期'],
            ['张三', '13800000000', '1栋', '1单元', '101', '居民', 80, '', 'monthly'],
            ['李商户', '13900000000', '商场', '一层', 'A-01', '商户', 45.5, '咖啡店', '季付'],
            ['坏数据', '13700000000', '2栋', '1单元', '', '居民', 60, '', 'monthly'],
        ])

        preview = client.post('/backoffice/imports/charge-targets/xlsx-preview', files={
            'xlsx_file': ('charge_targets.xlsx', content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
        })

        assert preview.status_code == 200, preview.text
        assert '导入预览' in preview.text
        assert '有效 2 行' in preview.text
        assert '错误 1 行' in preview.text
        assert '咖啡店' in preview.text
        assert 'quarterly' in preview.text
        assert '房号/铺位号' in preview.text

        repo = create_saas_repository(db_url)
        tenant = repo.list_tenants()[0]
        project = repo.list_projects(tenant['id'])[0]
        assert repo.list_charge_targets(tenant['id'], project['id']) == []
        repo.close()

        import_id = preview.text.split('name="import_id" value="')[1].split('"')[0]
        confirmed = client.post('/backoffice/imports/charge-targets/confirm', data={'import_id': import_id})

        assert confirmed.status_code == 200
        assert '成功导入：2' in confirmed.text
        assert '跳过错误：1' in confirmed.text
        targets = client.get('/api/charge-targets').json()['items']
        assert [item['room_number'] for item in targets] == ['101', 'A-01']
        assert targets[1]['shop_name'] == '咖啡店'
        assert targets[1]['payment_cycle'] == 'quarterly'


def test_xlsx_preview_rejects_other_file_types_without_writing():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = _client(db_url)

        response = client.post('/backoffice/imports/charge-targets/xlsx-preview', files={
            'xlsx_file': ('charge_targets.txt', b'not excel', 'text/plain'),
        })

        assert response.status_code == 400
        assert 'xlsx only' in response.text
        assert client.get('/api/charge-targets').json()['items'] == []
