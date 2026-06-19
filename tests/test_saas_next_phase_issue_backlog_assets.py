#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Next phase issue backlog assets for SaaS commercial roadmap."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_next_phase_issue_backlog_splits_candidates_into_executable_issues():
    doc = Path('docs/saas-next-phase-issue-backlog.md')
    assert doc.exists(), 'missing next phase issue backlog'
    text = doc.read_text(encoding='utf-8')
    required = [
        'SaaS 云端商业版下一阶段可执行工单清单',
        '工单拆分原则',
        '业主端 H5 工单包',
        '支付工单包',
        '授权云服务后台工单包',
        '桌面版存量业务迁移工单包',
        'ISSUE-H5-01',
        'ISSUE-PAY-01',
        'ISSUE-LIC-01',
        'ISSUE-MIG-01',
        '验收口径',
        '依赖关系',
        '风险边界',
        '不得与 SaaS 业务主库混用',
        '不得破坏租户数据隔离',
        '不得把客户上传数据与系统自身数据混在一起',
        'docs/saas-next-phase-decision-checklist.md',
        'docs/saas-day7-stability-review.md',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_next_phase_issue_backlog_check_script_passes_and_release_gate_includes_it():
    script = Path('scripts/saas_next_phase_issue_backlog_check.py')
    assert script.exists(), 'missing next phase issue backlog check script'
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
        'PASS saas next phase issue backlog doc',
        'PASS saas next phase issue backlog assets',
        'PASS saas next phase issue backlog page',
        'PASS saas next phase issue backlog release gate',
        'saas_next_phase_issue_backlog_check: PASS',
    ]:
        assert text in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_next_phase_issue_backlog_check.py' in gate


def test_acceptance_page_shows_next_phase_issue_backlog_without_internal_fields():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '工单拆分物业',
        'project_name': '工单拆分项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    for text in [
        'P0-20 下一阶段工单清单',
        'docs/saas-next-phase-issue-backlog.md',
        'scripts/saas_next_phase_issue_backlog_check.py',
        '业主端 H5 工单包',
        '支付工单包',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
