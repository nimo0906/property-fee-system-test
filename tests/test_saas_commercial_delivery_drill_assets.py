#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial delivery drill assets for SaaS backoffice."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_commercial_delivery_drill_doc_covers_empty_tenant_full_backoffice_flow():
    doc = Path('docs/saas-commercial-delivery-drill.md')
    assert doc.exists(), 'missing commercial delivery drill document'
    text = doc.read_text(encoding='utf-8')
    required = [
        'SaaS 云端商业版交付演示手册',
        '新租户从空库开始',
        '创建项目',
        '导入/录入收费对象',
        '配置收费项目',
        '生成账单',
        '账单审核',
        '登记收款',
        '查看欠费/实收报表',
        '导出账单或收款记录',
        '备份和恢复演练',
        '租户数据隔离',
        '客户上传数据与系统自身数据隔离',
        '正式商业后台',
        'scripts/saas_commercial_delivery_drill.py',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_commercial_delivery_drill_script_passes_and_reports_each_business_step():
    script = Path('scripts/saas_commercial_delivery_drill.py')
    assert script.exists(), 'missing commercial delivery drill script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for text in [
        'PASS commercial delivery tenant login',
        'PASS commercial delivery project context',
        'PASS commercial delivery charge targets',
        'PASS commercial delivery fee types',
        'PASS commercial delivery bill generation',
        'PASS commercial delivery bill approval',
        'PASS commercial delivery payments',
        'PASS commercial delivery reports',
        'PASS commercial delivery exports',
        'PASS commercial delivery backup restore drill',
        'PASS commercial delivery isolation',
        'saas_commercial_delivery_drill: PASS',
    ]:
        assert text in result.stdout


def test_commercial_delivery_drill_check_script_and_release_gate_cover_assets():
    script = Path('scripts/saas_commercial_delivery_drill_check.py')
    assert script.exists(), 'missing commercial delivery drill check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for text in [
        'PASS saas commercial delivery drill doc',
        'PASS saas commercial delivery drill script',
        'PASS saas commercial delivery readiness page',
        'PASS saas commercial delivery release gate',
        'saas_commercial_delivery_drill_check: PASS',
    ]:
        assert text in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_commercial_delivery_drill_check.py' in gate
    assert 'scripts/saas_commercial_delivery_drill.py' in gate


def test_acceptance_page_shows_p0_11_commercial_delivery_drill_without_internal_fields():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '交付演示物业',
        'project_name': '交付演示项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    for text in [
        'P0-11 商业交付演示',
        '新租户从空库开始',
        'docs/saas-commercial-delivery-drill.md',
        'scripts/saas_commercial_delivery_drill.py',
        'scripts/saas_commercial_delivery_drill_check.py',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
