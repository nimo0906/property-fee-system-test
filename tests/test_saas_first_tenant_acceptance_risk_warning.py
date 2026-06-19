#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant acceptance risk warning for incomplete fee review."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_first_tenant_acceptance_pages import ITEMS

FEE_ITEMS = [
    '推荐收费项目已初始化',
    '收费项目单价已按客户标准复核',
    '计费方式已确认',
    '业务模板与收费项目匹配',
]


def _client():
    client = TestClient(create_app())
    response = client.post('/api/auth/login', json={
        'tenant_name': '验收风险提示',
        'project_name': '验收风险项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert response.status_code == 200
    return client


def test_acceptance_page_warns_before_all_required_items_are_checked():
    client = _client()
    page = client.get('/backoffice/first-tenant-acceptance')
    assert page.status_code == 200
    for item in ['验收风险', '完成项不足', '金额配置复核未完成', '上线前请勿签收']:
        assert item in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_acceptance_page_shows_fee_review_risk_until_fee_items_checked():
    client = _client()
    partial = [item for item in ITEMS if item not in FEE_ITEMS]
    response = client.post('/backoffice/first-tenant-acceptance', data={
        'items': partial,
        'operator_name': '实施A',
        'customer_signer': '客户B',
        'notes': '未复核金额',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert '11 / 15' in response.text
    assert '金额配置复核未完成' in response.text
    assert '推荐收费项目已初始化、收费项目单价已按客户标准复核、计费方式已确认、业务模板与收费项目匹配' in response.text


def test_acceptance_print_export_show_risk_cleared_after_all_items_checked():
    client = _client()
    response = client.post('/backoffice/first-tenant-acceptance', data={
        'items': ITEMS,
        'operator_name': '实施A',
        'customer_signer': '客户B',
        'notes': '全部完成',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert '验收风险已解除' in response.text
    assert '15 / 15' in response.text
    printable = client.get('/backoffice/first-tenant-acceptance/print')
    export = client.get('/backoffice/first-tenant-acceptance/export.html')
    for page in [printable, export]:
        assert page.status_code == 200
        assert '验收风险已解除' in page.text
        assert '15 / 15' in page.text


def test_acceptance_risk_warning_check_script_is_in_release_gate():
    script = 'scripts/saas_first_tenant_acceptance_risk_warning_check.py'
    result = subprocess.run([sys.executable, script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
    assert result.returncode == 0, result.stdout
    assert script in Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
