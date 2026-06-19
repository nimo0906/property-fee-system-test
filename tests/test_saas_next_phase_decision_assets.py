#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Next phase decision checklist assets after SaaS day-7 review."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_next_phase_decision_checklist_covers_options_gates_and_boundaries():
    doc = Path('docs/saas-next-phase-decision-checklist.md')
    assert doc.exists(), 'missing next phase decision checklist'
    text = doc.read_text(encoding='utf-8')
    required = [
        'SaaS 云端商业版下一阶段立项决策清单',
        '立项前置条件',
        '候选方向',
        '业主端 H5',
        '微信/支付宝真实支付',
        '授权云服务后台',
        '更多桌面版存量业务迁移',
        '优先级建议',
        '进入条件',
        '不进入条件',
        '风险和边界',
        '不得与 SaaS 业务主库混用',
        '不得破坏租户数据隔离',
        '不得把客户上传数据与系统自身数据混在一起',
        'docs/saas-day7-stability-review.md',
        'release/saas-commercial-launch-report.pdf',
        'scripts/saas_release_gate.py',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_next_phase_decision_check_script_passes_and_release_gate_includes_it():
    script = Path('scripts/saas_next_phase_decision_check.py')
    assert script.exists(), 'missing next phase decision check script'
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
        'PASS saas next phase decision checklist doc',
        'PASS saas next phase decision checklist assets',
        'PASS saas next phase decision checklist page',
        'PASS saas next phase decision checklist release gate',
        'saas_next_phase_decision_check: PASS',
    ]:
        assert text in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_next_phase_decision_check.py' in gate


def test_acceptance_page_shows_next_phase_decision_without_internal_fields():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '立项决策物业',
        'project_name': '立项决策项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    for text in [
        'P0-19 下一阶段立项决策',
        'docs/saas-next-phase-decision-checklist.md',
        'scripts/saas_next_phase_decision_check.py',
        '业主端 H5',
        '微信/支付宝真实支付',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
