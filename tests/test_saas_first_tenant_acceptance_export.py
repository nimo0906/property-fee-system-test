#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Printable/exportable first tenant acceptance record."""

from fastapi.testclient import TestClient

from server.saas_app import create_app


def _admin_client_with_record():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '打印验收物业',
        'project_name': '打印验收项目',
        'username': 'tenant_admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    response = client.post('/backoffice/first-tenant-acceptance', data={
        'operator_name': '实施顾问A',
        'customer_signer': '客户负责人B',
        'notes': '打印版验收记录',
        'items': [
            '客户公司已创建', '项目已创建', '管理员已创建', '授权已绑定',
            '导入模板已确认', '收费项目已配置', '测试账单已生成', '测试收款已登记',
            '报表已核对', '租户隔离已验收', '备份恢复已演练',
        ],
    })
    assert response.status_code == 200
    return client


def test_acceptance_page_shows_print_and_export_links():
    client = _admin_client_with_record()
    page = client.get('/backoffice/first-tenant-acceptance')
    assert page.status_code == 200
    for text in [
        '打印版验收记录',
        '打印验收记录',
        '导出 HTML 验收记录',
        '/backoffice/first-tenant-acceptance/print',
        '/backoffice/first-tenant-acceptance/export.html',
    ]:
        assert text in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_printable_acceptance_record_contains_signature_blocks_and_print_css():
    client = _admin_client_with_record()
    page = client.get('/backoffice/first-tenant-acceptance/print')
    assert page.status_code == 200
    required = [
        '首租户交付验收记录（打印版）',
        '打印验收物业',
        '打印验收项目',
        '实施顾问A',
        '客户负责人B',
        '打印版验收记录',
        '11 / 11',
        '客户签字',
        '实施人员签字',
        '签收日期',
        '@media print',
        'window.print',
    ]
    for item in required:
        assert item in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_export_html_returns_downloadable_safe_html():
    client = _admin_client_with_record()
    response = client.get('/backoffice/first-tenant-acceptance/export.html')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    assert 'attachment; filename="first-tenant-acceptance.html"' in response.headers.get('content-disposition', '')
    assert '首租户交付验收记录（打印版）' in response.text
    assert '客户上传数据与系统自身数据隔离' in response.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in response.text


def test_acceptance_export_check_script_passes_and_gate_includes_it():
    import subprocess
    import sys
    from pathlib import Path

    script = Path('scripts/saas_first_tenant_acceptance_export_check.py')
    assert script.exists(), 'missing acceptance export check script'
    result = subprocess.run(
        [sys.executable, str(script)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_first_tenant_acceptance_export_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_first_tenant_acceptance_export_check.py' in gate
