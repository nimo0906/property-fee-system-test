#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant acceptance record fee type review checklist."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

FEE_REVIEW_ITEMS = [
    '推荐收费项目已初始化',
    '收费项目单价已按客户标准复核',
    '计费方式已确认',
    '业务模板与收费项目匹配',
]


def _client():
    client = TestClient(create_app())
    response = client.post('/api/auth/login', json={
        'tenant_name': '验收收费复核',
        'project_name': '验收收费复核项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200
    return client


def test_acceptance_page_includes_fee_type_review_items_without_internal_fields():
    client = _client()
    page = client.get('/backoffice/first-tenant-acceptance')
    assert page.status_code == 200
    for item in FEE_REVIEW_ITEMS:
        assert item in page.text
    assert '金额配置复核' in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_acceptance_record_save_and_print_include_fee_type_review_items():
    client = _client()
    response = client.post('/backoffice/first-tenant-acceptance', data={
        'items': FEE_REVIEW_ITEMS,
        'operator_name': '实施A',
        'customer_signer': '客户B',
        'notes': '收费项目已复核',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert '4 / 15' in response.text
    printable = client.get('/backoffice/first-tenant-acceptance/print')
    assert printable.status_code == 200
    for item in FEE_REVIEW_ITEMS:
        assert item in printable.text
    assert '收费项目已复核' in printable.text


def test_acceptance_export_and_checks_cover_fee_type_review_items():
    client = _client()
    export = client.get('/backoffice/first-tenant-acceptance/export.html')
    assert export.status_code == 200
    for item in FEE_REVIEW_ITEMS:
        assert item in export.text
    for script in [
        'scripts/saas_first_tenant_acceptance_record_check.py',
        'scripts/saas_first_tenant_acceptance_export_check.py',
    ]:
        result = subprocess.run([sys.executable, script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
        assert result.returncode == 0, result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_first_tenant_acceptance_fee_review_check.py' in gate
