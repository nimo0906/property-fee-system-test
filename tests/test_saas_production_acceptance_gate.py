#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-command production acceptance gate for SaaS delivery."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_acceptance_gate.py'
SCRIPT_REF = 'scripts/saas_production_acceptance_gate.py'


def test_production_acceptance_gate_dry_run_runs_ordered_sanitized_plan():
    assert SCRIPT.exists(), 'missing production acceptance gate script'
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--dry-run'],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    required = [
        'RUN scripts/saas_production_env_file_check.py --dry-run',
        'RUN scripts/saas_production_precheck.py --dry-run',
        'RUN scripts/saas_production_runtime_check.py --dry-run',
        'RUN scripts/saas_production_first_tenant_smoke.py --dry-run',
        'RUN scripts/saas_isolation_evidence.py',
        'RUN scripts/saas_release_evidence.py',
        'saas_production_acceptance_gate: PASS',
    ]
    last_index = -1
    for item in required:
        index = result.stdout.find(item)
        assert index > last_index, f'missing or out of order: {item}\n{result.stdout}'
        last_index = index
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo']:
        assert forbidden not in result.stdout


def test_production_acceptance_gate_local_mode_runs_business_smoke_and_evidence():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--local-testclient'],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for item in [
        'PASS first tenant smoke login',
        'PASS first tenant smoke reports and exports',
        'PASS first tenant smoke tenant isolation',
        'saas_isolation_evidence: PASS',
        'saas_release_evidence: PASS',
        'saas_production_acceptance_gate: PASS',
    ]:
        assert item in result.stdout
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo']:
        assert forbidden not in result.stdout


def test_production_acceptance_gate_is_registered_in_release_assets_docs_and_page():
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'scripts/saas_production_precheck.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
        ROOT / 'docs/saas-production-deployment-commands.md',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'

    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '一键验收物业',
        'project_name': '一键验收项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/deploy-checklist')
    assert page.status_code == 200
    for item in [
        '生产一键验收总入口',
        'scripts/saas_production_acceptance_gate.py',
        '.env 现场校验、生产预检、运行状态、首租户业务冒烟、租户隔离证据、上线证据报告',
        '--local-testclient',
    ]:
        assert item in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
