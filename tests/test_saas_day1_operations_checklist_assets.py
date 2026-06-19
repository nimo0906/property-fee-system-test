#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Day-1 operations checklist assets for SaaS commercial launch."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_day1_operations_checklist_covers_post_launch_monitoring_scope():
    doc = Path('docs/saas-day1-operations-checklist.md')
    assert doc.exists(), 'missing day-1 operations checklist'
    text = doc.read_text(encoding='utf-8')
    required = [
        'SaaS 云端商业版上线后首日巡检清单',
        '巡检时间点',
        'T+0 小时',
        'T+2 小时',
        'T+24 小时',
        '服务健康',
        '登录和权限',
        '租户隔离',
        '出账/收款抽查',
        '备份检查',
        '日志检查',
        '审计检查',
        '报表核对',
        '客户上传数据与系统自身数据隔离',
        '回退观察点',
        'scripts/saas_release_gate.py',
        'scripts/saas_backup.sh',
        'release/saas-isolation-evidence.md',
        'release/saas-release-evidence.md',
        '不得上线或必须回退',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_day1_operations_checklist_check_script_passes_and_release_gate_includes_it():
    script = Path('scripts/saas_day1_operations_checklist_check.py')
    assert script.exists(), 'missing day-1 operations checklist check script'
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
        'PASS saas day1 operations checklist doc',
        'PASS saas day1 operations checklist assets',
        'PASS saas day1 operations checklist page',
        'PASS saas day1 operations checklist release gate',
        'saas_day1_operations_checklist_check: PASS',
    ]:
        assert text in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_day1_operations_checklist_check.py' in gate


def test_acceptance_page_shows_day1_operations_checklist_without_internal_fields():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '首日巡检物业',
        'project_name': '首日巡检项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    for text in [
        'P0-17 首日巡检清单',
        'docs/saas-day1-operations-checklist.md',
        'scripts/saas_day1_operations_checklist_check.py',
        '服务健康',
        '回退观察点',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
