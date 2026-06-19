#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evidence file summary on production acceptance page."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_acceptance_evidence_summary_check.py'
SCRIPT_REF = 'scripts/saas_production_acceptance_evidence_summary_check.py'


def _login(client):
    return client.post('/api/auth/login', json={
        'tenant_name': '证据摘要物业',
        'project_name': '证据摘要项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })


def test_production_acceptance_page_reads_evidence_file_status_and_times():
    for rel in [
        'release/saas-production-acceptance-result.md',
        'release/saas-release-evidence.md',
        'release/saas-isolation-evidence.md',
    ]:
        path = ROOT / rel
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            path.write_text('# placeholder\n', encoding='utf-8')
    client = TestClient(create_app())
    assert _login(client).status_code == 200
    page = client.get('/backoffice/production-acceptance')
    assert page.status_code == 200
    for item in [
        '证据文件摘要',
        '验收留档：存在',
        '上线证据：存在',
        '隔离证据：存在',
        '最近生成时间',
        'release/saas-production-acceptance-result.md',
        'release/saas-release-evidence.md',
        'release/saas-isolation-evidence.md',
    ]:
        assert item in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo']:
        assert hidden not in page.text


def test_evidence_summary_helper_reports_missing_files_without_throwing(tmp_path):
    from server.saas_production_acceptance_pages import evidence_summary

    rows = evidence_summary(tmp_path)
    assert len(rows) == 3
    assert all(row['status'] == '缺失' for row in rows)
    assert all(row['updated_at'] == '未生成' for row in rows)
    assert {row['label'] for row in rows} == {'验收留档', '上线证据', '隔离证据'}


def test_evidence_summary_check_is_registered_and_passes():
    assert SCRIPT.exists(), 'missing evidence summary check script'
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for item in [
        'PASS production acceptance evidence summary page',
        'PASS production acceptance evidence summary helper',
        'PASS production acceptance evidence summary registry',
        'saas_production_acceptance_evidence_summary_check: PASS',
    ]:
        assert item in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'
