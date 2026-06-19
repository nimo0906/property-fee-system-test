#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First tenant delivery acceptance record page."""

from fastapi.testclient import TestClient

from server.saas_app import create_app


def _admin_client():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '验收记录物业',
        'project_name': '验收记录项目',
        'username': 'tenant_admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    return client


def test_acceptance_record_page_shows_checklist_and_no_internal_fields():
    client = _admin_client()
    page = client.get('/backoffice/first-tenant-acceptance')
    assert page.status_code == 200
    required = [
        '首租户交付验收记录',
        '客户公司已创建',
        '项目已创建',
        '管理员已创建',
        '授权已绑定',
        '导入模板已确认',
        '收费项目已配置',
        '测试账单已生成',
        '测试收款已登记',
        '报表已核对',
        '租户隔离已验收',
        '备份恢复已演练',
        '实施人员',
        '客户签收人',
        '保存验收记录',
        '客户上传数据与系统自身数据隔离',
    ]
    for item in required:
        assert item in page.text
    assert 'action="/backoffice/first-tenant-acceptance"' in page.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in page.text


def test_acceptance_record_submit_persists_in_memory_page_without_sensitive_values():
    client = _admin_client()
    response = client.post('/backoffice/first-tenant-acceptance', data={
        'operator_name': '实施顾问A',
        'customer_signer': '客户负责人B',
        'notes': '首租户上线验收完成',
        'items': [
            '客户公司已创建', '项目已创建', '管理员已创建', '授权已绑定',
            '导入模板已确认', '收费项目已配置', '测试账单已生成', '测试收款已登记',
            '报表已核对', '租户隔离已验收', '备份恢复已演练',
        ],
    }, follow_redirects=True)
    assert response.status_code == 200
    for text in ['验收记录已保存', '实施顾问A', '客户负责人B', '首租户上线验收完成', '11 / 11']:
        assert text in response.text
    for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        assert hidden not in response.text


def test_acceptance_record_requires_admin_role():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '只读物业',
        'project_name': '只读项目',
        'username': 'reader',
        'role_code': 'executive',
    })
    assert login.status_code == 200
    assert client.get('/backoffice/first-tenant-acceptance').status_code == 403


def test_acceptance_record_check_script_passes_and_gate_includes_it():
    import subprocess
    import sys
    from pathlib import Path

    script = Path('scripts/saas_first_tenant_acceptance_record_check.py')
    assert script.exists(), 'missing acceptance record check script'
    result = subprocess.run(
        [sys.executable, str(script)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_first_tenant_acceptance_record_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_first_tenant_acceptance_record_check.py' in gate
