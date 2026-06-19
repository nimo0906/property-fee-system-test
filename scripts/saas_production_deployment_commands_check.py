#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production deployment command runbook for SaaS Linux/VPS delivery."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app

SCRIPT = 'scripts/saas_production_deployment_commands_check.py'
DOC = 'docs/saas-production-deployment-commands.md'
FORBIDDEN = ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo']


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def read(path):
    return (ROOT / path).read_text(encoding='utf-8') if (ROOT / path).exists() else ''


def check_doc():
    text = read(DOC)
    required = [
        'SaaS 生产部署实施命令清单', '通用 Linux/VPS', 'cp .env.example .env',
        'chmod 600 .env', 'docker compose pull', 'docker compose up -d',
        'sudo install -m 0644 deploy/systemd/property-saas.service /etc/systemd/system/property-saas.service',
        'sudo systemctl daemon-reload', 'sudo systemctl enable --now property-saas',
        'sudo systemctl status property-saas --no-pager',
        'curl -fsS http://127.0.0.1:8000/health',
        'curl -fsS https://your-domain.example.com/login',
        'PYTHONPYCACHEPREFIX=/tmp/property_pycache python3 scripts/saas_release_gate.py',
        '客户上传数据与系统自身数据隔离', '失败即停止交付',
    ]
    for item in required:
        require(item in text, f'missing deployment command doc item: {item}')
    for item in FORBIDDEN:
        require(item not in text, f'forbidden content in deployment command doc: {item}')
    print('PASS production deployment commands doc')


def check_page():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '部署命令检查物业', 'project_name': '部署命令检查项目',
        'username': 'admin', 'role_code': 'system_admin',
    })
    require(login.status_code == 200, 'login failed')
    page = client.get('/backoffice/deploy-checklist')
    require(page.status_code == 200, 'deploy checklist failed')
    for item in [
        '生产部署实施命令', DOC, SCRIPT, 'cp .env.example .env',
        'sudo systemctl daemon-reload', 'sudo systemctl enable --now property-saas',
        'curl -fsS http://127.0.0.1:8000/health',
        'curl -fsS https://your-domain.example.com/login',
    ]:
        require(item in page.text, f'missing deployment command page item: {item}')
    for item in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(item not in page.text, f'forbidden content in deploy page: {item}')
    print('PASS production deployment commands page')


def check_gate():
    for path in [
        'scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py',
        'server/saas_deploy.py', 'server/saas_commercial_readiness.py',
    ]:
        require(SCRIPT in read(path), f'missing production deployment command check in {path}')
    print('PASS production deployment commands gate')


def main():
    check_doc()
    check_page()
    check_gate()
    print('saas_production_deployment_commands_check: PASS')


if __name__ == '__main__':
    main()
