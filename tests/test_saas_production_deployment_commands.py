#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production deployment command runbook for SaaS Linux/VPS delivery."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-production-deployment-commands.md'
CHECK = ROOT / 'scripts/saas_production_deployment_commands_check.py'
SCRIPT = 'scripts/saas_production_deployment_commands_check.py'


def test_production_deployment_commands_doc_lists_exact_linux_steps_without_secret_leaks():
    assert DOC.exists(), 'missing production deployment commands doc'
    text = DOC.read_text(encoding='utf-8')
    required = [
        'SaaS 生产部署实施命令清单',
        '通用 Linux/VPS',
        'cp .env.example .env',
        'chmod 600 .env',
        'docker compose pull',
        'docker compose up -d',
        'sudo install -m 0644 deploy/systemd/property-saas.service /etc/systemd/system/property-saas.service',
        'sudo systemctl daemon-reload',
        'sudo systemctl enable --now property-saas',
        'sudo systemctl status property-saas --no-pager',
        'curl -fsS http://127.0.0.1:8000/health',
        'curl -fsS https://your-domain.example.com/login',
        'PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_release_gate.py',
        '客户上传数据与系统自身数据隔离',
        '失败即停止交付',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo', 'P@ssw0rd', '0123456789abcdef']:
        assert forbidden not in text


def test_production_deployment_commands_check_script_passes_and_is_registered():
    assert CHECK.exists(), 'missing production deployment commands check script'
    result = subprocess.run(
        [sys.executable, str(CHECK)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for item in [
        'PASS production deployment commands doc',
        'PASS production deployment commands page',
        'PASS production deployment commands gate',
        'saas_production_deployment_commands_check: PASS',
    ]:
        assert item in result.stdout
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo']:
        assert forbidden not in result.stdout
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT in path.read_text(encoding='utf-8'), f'missing {SCRIPT} in {path}'


def test_deploy_checklist_page_shows_production_commands_without_sensitive_fields():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '命令清单物业',
        'project_name': '命令清单项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/deploy-checklist')
    assert page.status_code == 200
    for item in [
        '生产部署实施命令',
        'docs/saas-production-deployment-commands.md',
        'scripts/saas_production_deployment_commands_check.py',
        'cp .env.example .env',
        'sudo systemctl daemon-reload',
        'sudo systemctl enable --now property-saas',
        'curl -fsS http://127.0.0.1:8000/health',
        'curl -fsS https://your-domain.example.com/login',
    ]:
        assert item in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id', '/Users/nimo']:
        assert hidden not in page.text
