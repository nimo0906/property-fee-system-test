#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production deployment precheck assets for SaaS commercial delivery."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

SCRIPT = Path('scripts/saas_production_precheck.py')
DOC = Path('docs/saas-production-precheck.md')
NGINX = Path('deploy/nginx/property-saas.conf')


def test_production_precheck_script_exists_and_reports_required_sections():
    assert SCRIPT.exists(), 'missing production precheck script'
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--dry-run'],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    required = [
        'PASS production precheck assets',
        'PASS production precheck environment contract',
        'PASS production precheck ports',
        'PASS production precheck storage directories',
        'PASS production precheck docker compose',
        'PASS production precheck nginx tls',
        'PASS production precheck systemd',
        'PASS production precheck logrotate',
        'PASS production precheck backup restore assets',
        'PASS production precheck license binding assets',
        'PASS production precheck evidence assets',
        'saas_production_precheck: PASS',
    ]
    for item in required:
        assert item in result.stdout
    for hidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo']:
        assert hidden not in result.stdout


def test_production_precheck_doc_covers_server_operator_usage_and_no_secret_leaks():
    assert DOC.exists(), 'missing production precheck document'
    text = DOC.read_text(encoding='utf-8')
    required = [
        'SaaS 生产部署一键自检说明',
        'scripts/saas_production_precheck.py --dry-run',
        'scripts/saas_production_precheck.py',
        '服务器环境',
        '端口与反向代理',
        '客户上传数据目录',
        '系统自身数据目录',
        '备份目录',
        '日志目录',
        'Docker Compose',
        'Nginx HTTPS',
        'systemd',
        'logrotate',
        '备份恢复脚本',
        '授权绑定文件',
        '上线证据文件',
        '失败即停止交付',
        '不提交真实 .env',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_production_precheck_is_registered_in_gate_registry_readiness_and_deploy_page():
    for path in [
        Path('scripts/saas_release_gate.py'),
        Path('scripts/saas_release_evidence.py'),
        Path('server/saas_deploy.py'),
        Path('server/saas_commercial_readiness.py'),
    ]:
        text = path.read_text(encoding='utf-8')
        assert 'scripts/saas_production_precheck.py' in text, f'missing script in {path}'
    assert 'docs/saas-production-precheck.md' in Path('server/saas_deploy.py').read_text(encoding='utf-8')
    assert 'docs/saas-production-precheck.md' in Path('server/saas_commercial_readiness.py').read_text(encoding='utf-8')

    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '生产自检物业',
        'project_name': '生产自检项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/deploy-checklist')
    assert page.status_code == 200
    for text in [
        '生产部署一键自检',
        'scripts/saas_production_precheck.py',
        'docs/saas-production-precheck.md',
        '服务器环境',
        '端口与反向代理',
        '客户上传数据目录',
        '系统自身数据目录',
        '备份目录',
        '日志目录',
        '授权绑定文件',
        '上线证据文件',
        '失败即停止交付',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text


def test_nginx_asset_terminates_https_and_redirects_http_without_exposing_app_directly():
    text = NGINX.read_text(encoding='utf-8')
    assert 'listen 80' in text
    assert 'return 301 https://$host$request_uri' in text
    assert 'listen 443 ssl' in text
    assert 'ssl_certificate' in text
    assert 'proxy_pass http://127.0.0.1:8000' in text
    assert 'POSTGRES_PASSWORD' not in text
    assert 'APP_SECRET_KEY' not in text
