#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backoffice batch bill preview tests."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def login_client(database_url):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': '批量预览物业', 'project_name': '批量预览项目', 'username': 'finance', 'role_code': 'finance'
    })
    assert response.status_code == 200
    return client

def test_backoffice_batch_generate_preview_does_not_write_until_confirmed():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = login_client(db_url)
        client.post('/api/charge-targets', json={'building': '预览区', 'unit': '一层', 'room_number': 'P-101', 'category': '商户', 'area': 40})
        client.post('/api/charge-targets', json={'building': '预览区', 'unit': '一层', 'room_number': 'P-102', 'category': '商户', 'area': 60})
        fee = client.post('/api/fee-types', json={'name': '预览物业费', 'unit_price': 2, 'billing_mode': 'area'}).json()['item']
        first = client.post('/api/bills/batch-generate', json={
            'fee_type_id': fee['id'], 'billing_period': '2028-02',
            'service_start': '2028-02-01', 'service_end': '2028-02-29',
            'category': '商户', 'building': '预览区', 'unit': '一层',
        })
        assert first.status_code == 200
        assert first.json()['created_count'] == 2
        client.post('/api/charge-targets', json={'building': '预览区', 'unit': '一层', 'room_number': 'P-103', 'category': '商户', 'area': 70})

        preview = client.post('/backoffice/bills/batch-generate-preview', data={
            'fee_type_id': str(fee['id']), 'billing_period': '2028-02',
            'service_start': '2028-02-01', 'service_end': '2028-02-29',
            'category': '商户', 'building': '预览区', 'unit': '一层',
        })

        assert preview.status_code == 200
        assert '批量出账预览' in preview.text
        assert '预计出账1张' in preview.text
        assert '跳过2张' in preview.text
        assert '金额合计140.0元' in preview.text
        assert 'P-103 2028-02-01~2028-02-29 140.0元' in preview.text
        assert 'P-101 已存在账单，确认导入将跳过' in preview.text
        repo = create_saas_repository(db_url)
        tenant = repo.list_tenants()[0]
        project = repo.list_projects(tenant['id'])[0]
        assert len(repo.list_bills(tenant['id'], project['id'], '2028-02')) == 2
        repo.close()

        confirmed = client.post('/backoffice/bills/batch-generate-confirm', data={
            'fee_type_id': str(fee['id']), 'billing_period': '2028-02',
            'service_start': '2028-02-01', 'service_end': '2028-02-29',
            'category': '商户', 'building': '预览区', 'unit': '一层',
        }, follow_redirects=False)

        assert confirmed.status_code == 303
        page = client.get(confirmed.headers['location'])
        assert '批量出账1张，跳过2张，金额合计140.0元' in page.text
        repo = create_saas_repository(db_url)
        assert len(repo.list_bills(tenant['id'], project['id'], '2028-02')) == 3
        repo.close()


