#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-page operator launch runbook assets for SaaS commercial deployment."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_operator_one_page_runbook_covers_exact_launch_sequence():
    doc = Path('docs/saas-operator-one-page-runbook.md')
    assert doc.exists(), 'missing operator one-page runbook'
    text = doc.read_text(encoding='utf-8')
    required = [
        'SaaS 云端商业版实施人员一页式上线操作指引',
        '执行顺序',
        '1. 准备服务器',
        '2. 配置环境变量',
        '3. 启动服务',
        '4. 运行上线门禁',
        '5. 执行业务演示',
        '6. 执行备份恢复演练',
        '7. 核对租户隔离',
        '8. 完成客户签收',
        '9. 留存上线报告',
        '10. 回退条件',
        'docker compose up -d',
        'scripts/saas_release_gate.py',
        'scripts/saas_commercial_delivery_drill.py',
        'scripts/saas_backup.sh',
        'scripts/saas_restore.sh --verify-metadata',
        'release/saas-commercial-launch-report.pdf',
        'docs/saas-customer-acceptance-signoff.md',
        '客户上传数据与系统自身数据隔离',
        '租户数据隔离',
        '不提交真实 .env',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_operator_one_page_runbook_check_script_passes_and_release_gate_includes_it():
    script = Path('scripts/saas_operator_one_page_runbook_check.py')
    assert script.exists(), 'missing operator one-page runbook check script'
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
        'PASS saas operator one-page runbook doc',
        'PASS saas operator one-page runbook assets',
        'PASS saas operator one-page runbook page',
        'PASS saas operator one-page runbook release gate',
        'saas_operator_one_page_runbook_check: PASS',
    ]:
        assert text in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_operator_one_page_runbook_check.py' in gate


def test_acceptance_page_shows_operator_runbook_without_internal_fields():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '实施指引物业',
        'project_name': '实施指引项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    for text in [
        'P0-16 一页式上线指引',
        'docs/saas-operator-one-page-runbook.md',
        'scripts/saas_operator_one_page_runbook_check.py',
        '执行顺序',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
