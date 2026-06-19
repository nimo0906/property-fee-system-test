#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal launch package assets for SaaS commercial cloud delivery."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_minimal_launch_package_manifest_lists_required_delivery_assets():
    doc = Path('docs/saas-minimal-launch-package.md')
    assert doc.exists(), 'missing minimal launch package manifest'
    text = doc.read_text(encoding='utf-8')
    required = [
        'SaaS 云端商业版最小上线包清单',
        '上线包范围',
        '部署配置',
        '运行服务',
        '数据隔离',
        '验收演示',
        '运维备份',
        '上线证据',
        'docker-compose.yml',
        '.env.example',
        'deploy/nginx/property-saas.conf',
        'deploy/systemd/property-saas.service',
        'deploy/logrotate/property-saas',
        'scripts/saas_release_gate.py',
        'scripts/saas_commercial_delivery_drill.py',
        'scripts/saas_commercial_delivery_drill_check.py',
        'scripts/saas_deployment_drill_check.py',
        'scripts/saas_backup.sh',
        'scripts/saas_restore.sh',
        'docs/saas-cloud-deployment-drill.md',
        'docs/saas-commercial-delivery-drill.md',
        'release/saas-release-evidence.md',
        '不提交真实 .env',
        '不包含业主端 H5、微信/支付宝真实支付',
        '客户上传数据与系统自身数据隔离',
        '租户数据隔离',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_minimal_launch_package_check_script_passes_and_release_gate_includes_it():
    script = Path('scripts/saas_minimal_launch_package_check.py')
    assert script.exists(), 'missing minimal launch package check script'
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
        'PASS saas minimal launch package manifest',
        'PASS saas minimal launch package assets',
        'PASS saas minimal launch package pages',
        'PASS saas minimal launch package release gate',
        'saas_minimal_launch_package_check: PASS',
    ]:
        assert text in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_minimal_launch_package_check.py' in gate


def test_deploy_and_acceptance_pages_show_minimal_launch_package_without_secrets():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '上线包物业',
        'project_name': '上线包项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    deploy = client.get('/backoffice/deploy-checklist')
    acceptance = client.get('/backoffice/acceptance')
    assert deploy.status_code == 200
    assert acceptance.status_code == 200
    for page_text in [deploy.text, acceptance.text]:
        for text in [
            '最小上线包',
            'docs/saas-minimal-launch-package.md',
            'scripts/saas_minimal_launch_package_check.py',
            '不提交真实 .env',
            '客户上传数据与系统自身数据隔离',
        ]:
            assert text in page_text
        for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
            assert hidden not in page_text
