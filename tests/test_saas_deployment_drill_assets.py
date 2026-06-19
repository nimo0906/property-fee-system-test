#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deployment drill assets for SaaS commercial cloud release."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_deployment_drill_doc_covers_generic_vps_tencent_aliyun_and_ops_scope():
    doc = Path('docs/saas-cloud-deployment-drill.md')
    assert doc.exists(), 'missing deployment drill document'
    text = doc.read_text(encoding='utf-8')
    required = [
        'SaaS 云端商业版部署演练手册',
        '通用 Linux/VPS',
        '腾讯云',
        '阿里云',
        '.env.example',
        '不提交真实 .env',
        'docker compose up -d',
        'deploy/nginx/property-saas.conf',
        'HTTPS',
        'deploy/systemd/property-saas.service',
        'deploy/logrotate/property-saas',
        'scripts/saas_backup.sh',
        'scripts/saas_restore.sh --verify-metadata',
        'scripts/saas_release_gate.py',
        'scripts/saas_commercial_readiness_check.py',
        '客户上传数据与系统自身数据隔离',
        '租户数据隔离',
        '回退与故障处理',
        '暂不包含业主端 H5、微信/支付宝真实支付',
    ]
    for item in required:
        assert item in text
    forbidden = ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']
    for item in forbidden:
        assert item not in text


def test_deployment_drill_check_script_passes_and_is_in_release_gate():
    script = Path('scripts/saas_deployment_drill_check.py')
    assert script.exists(), 'missing deployment drill check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for text in [
        'PASS saas deployment drill doc',
        'PASS saas deployment assets',
        'PASS saas deployment drill page',
        'PASS saas deployment drill gate',
        'saas_deployment_drill_check: PASS',
    ]:
        assert text in result.stdout

    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_deployment_drill_check.py' in gate


def test_deploy_checklist_shows_cloud_deployment_drill_assets_without_secrets():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '部署演练物业',
        'project_name': '部署演练项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200

    page = client.get('/backoffice/deploy-checklist')
    assert page.status_code == 200
    for text in [
        '云端部署演练',
        '通用 Linux/VPS',
        '腾讯云',
        '阿里云',
        'docs/saas-cloud-deployment-drill.md',
        'scripts/saas_deployment_drill_check.py',
        'scripts/saas_commercial_readiness_check.py',
        '客户上传数据与系统自身数据隔离',
        '暂不包含业主端 H5、微信/支付宝真实支付',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
