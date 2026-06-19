#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formal DOCX/PDF launch report assets for SaaS commercial release."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_formal_launch_report_docx_pdf_assets_exist_and_are_checked():
    docx = Path('release/saas-commercial-launch-report.docx')
    pdf = Path('release/saas-commercial-launch-report.pdf')
    assert docx.exists(), 'missing formal launch report docx'
    assert pdf.exists(), 'missing formal launch report pdf'
    assert docx.stat().st_size > 10_000
    assert pdf.stat().st_size > 10_000

    script = Path('scripts/saas_formal_launch_report_check.py')
    assert script.exists(), 'missing formal launch report check script'
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
        'PASS saas formal launch report docx',
        'PASS saas formal launch report pdf',
        'PASS saas formal launch report formatting',
        'PASS saas formal launch report page',
        'PASS saas formal launch report release gate',
        'saas_formal_launch_report_check: PASS',
    ]:
        assert text in result.stdout


def test_formal_launch_report_docx_contains_required_business_sections_and_no_secrets():
    import re
    import zipfile

    with zipfile.ZipFile('release/saas-commercial-launch-report.docx') as zf:
        xml = zf.read('word/document.xml').decode('utf-8')
    text = re.sub(r'<[^>]+>', '', xml)
    required = [
        'SaaS 云端商业版上线总报告',
        '总体结论',
        'P0-1 到 P0-13 完成状态',
        '验证命令',
        '部署资产',
        '演示路径',
        '签收路径',
        '租户数据隔离',
        '客户上传数据与系统自身数据隔离',
        '不包含业主端 H5、微信/支付宝真实支付',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_acceptance_page_shows_formal_launch_report_without_internal_fields():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '正式报告物业',
        'project_name': '正式报告项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    for text in [
        'P0-15 正式报告文件',
        'release/saas-commercial-launch-report.docx',
        'release/saas-commercial-launch-report.pdf',
        'scripts/saas_formal_launch_report_check.py',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
