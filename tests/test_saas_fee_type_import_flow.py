#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fee type import preview/confirm flow tests for SaaS."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_repository import create_saas_repository


def _client(database_url=None, tenant='收费项目导入物业', project='收费项目导入项目'):
    client = TestClient(create_app(database_url=database_url))
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': 'finance',
        'role_code': 'finance',
    })
    assert response.status_code == 200
    return client


def test_fee_type_import_preview_does_not_write_and_confirm_writes_valid_rows_only():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client = _client(db_url)
        rows = [
            {'name': '物业费', 'unit_price': '2.5', 'billing_mode': 'area'},
            {'收费项目': '租金', '单价': '1200', '计费方式': 'fixed'},
            {'name': '', 'unit_price': '1', 'billing_mode': 'area'},
            {'name': '坏单价', 'unit_price': 'bad', 'billing_mode': 'area'},
        ]

        preview = client.post('/api/imports/fee-types/preview', json={'rows': rows})

        assert preview.status_code == 200, preview.text
        assert preview.json()['valid_count'] == 2
        assert preview.json()['error_count'] == 2
        repo = create_saas_repository(db_url)
        tenant = repo.list_tenants()[0]
        project = repo.list_projects(tenant['id'])[0]
        assert repo.list_fee_types(tenant['id'], project['id']) == []
        repo.close()

        review = client.get(f"/api/imports/fee-types/{preview.json()['import_id']}/review")
        assert review.status_code == 200
        assert review.json()['valid_rows'][0]['name'] == '物业费'
        assert review.json()['valid_rows'][1]['billing_mode'] == 'fixed'
        assert review.json()['errors'][0]['row'] == 3

        confirmed = client.post('/api/imports/fee-types/confirm', json={'import_id': preview.json()['import_id']})
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json() == {'created_count': 2, 'skipped_count': 2}
        fees = client.get('/api/fee-types').json()['items']
        assert [(row['name'], row['unit_price'], row['billing_mode']) for row in fees] == [
            ('物业费', 2.5, 'area'),
            ('租金', 1200.0, 'fixed'),
        ]


def test_fee_type_import_is_idempotent_and_tenant_scoped():
    with tempfile.TemporaryDirectory() as td:
        db_url = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        client_a = _client(db_url, tenant='A收费项目导入物业', project='A项目')
        preview = client_a.post('/api/imports/fee-types/preview', json={'rows': [
            {'name': '物业费', 'unit_price': '3', 'billing_mode': 'area'},
        ]})
        import_id = preview.json()['import_id']

        client_b = _client(db_url, tenant='B收费项目导入物业', project='B项目')
        assert client_b.get(f'/api/imports/fee-types/{import_id}/review').status_code == 403
        assert client_b.post('/api/imports/fee-types/confirm', json={'import_id': import_id}).status_code == 403

        first = client_a.post('/api/imports/fee-types/confirm', json={'import_id': import_id})
        second = client_a.post('/api/imports/fee-types/confirm', json={'import_id': import_id})
        assert first.json() == {'created_count': 1, 'skipped_count': 0}
        assert second.json() == {'created_count': 0, 'skipped_count': 0}
        assert len(client_a.get('/api/fee-types').json()['items']) == 1


def test_fee_type_import_template_page_and_csv_are_safe():
    client = _client()

    page = client.get('/backoffice/imports/templates/fee-types')
    csv = client.get('/api/imports/templates/fee-types.csv')

    assert page.status_code == 200
    for text in ['收费项目导入模板', '收费项目', '单价', '计费方式', 'area', 'fixed', '导入预览不会写库']:
        assert text in page.text
    assert csv.status_code == 200
    assert 'text/csv' in csv.headers.get('content-type', '')
    assert csv.text.splitlines()[0] == 'name,unit_price,billing_mode'
    assert '物业费,2.5,area' in csv.text
    for hidden in ['tenant_id', 'project_id', 'APP_SECRET_KEY', 'POSTGRES_PASSWORD']:
        assert hidden not in page.text
        assert hidden not in csv.text
