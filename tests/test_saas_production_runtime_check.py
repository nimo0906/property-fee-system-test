#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production runtime status check for SaaS Linux/VPS deployment."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_runtime_check.py'
SCRIPT_REF = 'scripts/saas_production_runtime_check.py'


def test_runtime_check_dry_run_lists_post_start_checks_without_running_server_tools():
    assert SCRIPT.exists(), 'missing production runtime check script'
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
        'PASS runtime check plan docker compose ps',
        'PASS runtime check plan systemctl is-active property-saas',
        'PASS runtime check plan health endpoint',
        'PASS runtime check plan login endpoint',
        'PASS runtime check plan localhost port binding',
        'PASS runtime check plan nginx config',
        'PASS runtime check plan log directory writable',
        'saas_production_runtime_check: PASS',
    ]
    for item in required:
        assert item in result.stdout
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo']:
        assert forbidden not in result.stdout


def test_runtime_check_mock_mode_verifies_real_command_results_and_failures(tmp_path):
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()
    ok = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            '--docker-cmd', 'printf "app Up\\npostgres Up\\n"',
            '--systemctl-cmd', 'printf active',
            '--health-cmd', 'printf "{\\"ok\\":true}"',
            '--login-cmd', 'printf "<html>login</html>"',
            '--ports-cmd', 'printf "127.0.0.1:8000"',
            '--nginx-cmd', 'printf "syntax is ok"',
            '--log-dir', str(log_dir),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert ok.returncode == 0, ok.stdout
    for item in [
        'PASS runtime docker compose ps',
        'PASS runtime systemd active',
        'PASS runtime health endpoint',
        'PASS runtime login endpoint',
        'PASS runtime localhost port binding',
        'PASS runtime nginx config',
        'PASS runtime log directory writable',
    ]:
        assert item in ok.stdout

    bad_ports = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            '--docker-cmd', 'printf "app Up\\npostgres Up\\n"',
            '--systemctl-cmd', 'printf active',
            '--health-cmd', 'printf ok',
            '--login-cmd', 'printf login',
            '--ports-cmd', 'printf "0.0.0.0:8000"',
            '--nginx-cmd', 'printf ok',
            '--log-dir', str(log_dir),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert bad_ports.returncode != 0
    assert 'runtime port binding must stay on 127.0.0.1' in bad_ports.stdout


def test_runtime_check_is_registered_in_gate_evidence_docs_and_deploy_page():
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
        'tenant_name': '运行状态校验物业',
        'project_name': '运行状态校验项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/deploy-checklist')
    assert page.status_code == 200
    for item in [
        '生产运行状态自检',
        'scripts/saas_production_runtime_check.py',
        'docker compose ps',
        'systemctl is-active property-saas',
        'curl -fsS http://127.0.0.1:8000/health',
        '确认 app 只监听本机端口',
    ]:
        assert item in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
