#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production first tenant business smoke drill for SaaS delivery."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_first_tenant_smoke.py'
SCRIPT_REF = 'scripts/saas_production_first_tenant_smoke.py'


def test_first_tenant_smoke_dry_run_lists_business_closure_without_customer_data():
    assert SCRIPT.exists(), 'missing first tenant smoke script'
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--dry-run'],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    required = [
        'PASS first tenant smoke plan login',
        'PASS first tenant smoke plan project context',
        'PASS first tenant smoke plan charge targets',
        'PASS first tenant smoke plan fee types',
        'PASS first tenant smoke plan bill generation',
        'PASS first tenant smoke plan payment registration',
        'PASS first tenant smoke plan reports and exports',
        'PASS first tenant smoke plan tenant isolation',
        'saas_production_first_tenant_smoke: PASS',
    ]
    for item in required:
        assert item in result.stdout
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo']:
        assert forbidden not in result.stdout


def test_first_tenant_smoke_local_mode_runs_minimum_business_closure_and_isolation():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--local-testclient'],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for item in [
        'PASS first tenant smoke login',
        'PASS first tenant smoke project context',
        'PASS first tenant smoke charge targets',
        'PASS first tenant smoke fee types',
        'PASS first tenant smoke bill generation',
        'PASS first tenant smoke bill approval',
        'PASS first tenant smoke payment registration',
        'PASS first tenant smoke reports and exports',
        'PASS first tenant smoke tenant isolation',
        'saas_production_first_tenant_smoke: PASS',
    ]:
        assert item in result.stdout
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo']:
        assert forbidden not in result.stdout


def test_first_tenant_smoke_is_registered_in_gate_evidence_docs_and_deploy_page():
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
        'tenant_name': '首租户冒烟物业',
        'project_name': '首租户冒烟项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/deploy-checklist')
    assert page.status_code == 200
    for item in [
        '首租户业务冒烟',
        'scripts/saas_production_first_tenant_smoke.py',
        '登录、收费对象、收费项目、出账、收款、报表、导出、租户隔离',
        '--base-url https://your-domain.example.com',
    ]:
        assert item in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
