#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Customer acceptance sign-off assets for SaaS commercial launch."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_customer_acceptance_signoff_doc_covers_manual_launch_checklist():
    doc = Path('docs/saas-customer-acceptance-signoff.md')
    assert doc.exists(), 'missing customer acceptance signoff document'
    text = doc.read_text(encoding='utf-8')
    required = [
        'SaaS 云端商业版上线前人工验收与客户交付签收清单',
        '客户信息',
        '部署完成确认',
        '最小上线包确认',
        '商业交付演示通过',
        '备份恢复演练通过',
        '租户隔离通过',
        '账号权限确认',
        '客户上传数据与系统自身数据隔离确认',
        '数据不混用确认',
        '上线证据确认',
        '问题与遗留事项',
        '客户签收',
        '实施人员签收',
        'scripts/saas_release_gate.py',
        'scripts/saas_minimal_launch_package_check.py',
        'release/saas-release-evidence.md',
        'release/saas-isolation-evidence.md',
        '不提交真实 .env',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_customer_acceptance_signoff_check_script_passes_and_release_gate_includes_it():
    script = Path('scripts/saas_customer_acceptance_signoff_check.py')
    assert script.exists(), 'missing customer signoff check script'
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
        'PASS saas customer acceptance signoff doc',
        'PASS saas customer acceptance signoff assets',
        'PASS saas customer acceptance signoff page',
        'PASS saas customer acceptance signoff release gate',
        'saas_customer_acceptance_signoff_check: PASS',
    ]:
        assert text in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_customer_acceptance_signoff_check.py' in gate


def test_acceptance_page_shows_customer_signoff_without_internal_fields():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '签收物业',
        'project_name': '签收项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    for text in [
        'P0-13 客户交付签收',
        '上线前人工验收',
        'docs/saas-customer-acceptance-signoff.md',
        'scripts/saas_customer_acceptance_signoff_check.py',
        '部署完成确认',
        '数据不混用确认',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
