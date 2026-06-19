#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production-like deployment rehearsal assets for SaaS commercial release."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

DOC = Path('docs/saas-production-deployment-rehearsal.md')
SCRIPT = Path('scripts/saas_production_deployment_rehearsal_check.py')


def test_production_deployment_rehearsal_doc_covers_real_vps_delivery_loop():
    assert DOC.exists(), 'missing production deployment rehearsal document'
    text = DOC.read_text(encoding='utf-8')
    required = [
        'SaaS 商业版实机部署演练验收清单',
        '通用 Linux/VPS',
        '腾讯云 CVM',
        '阿里云 ECS',
        'SSH 登录与基础环境',
        'Docker Compose 启动',
        'Nginx HTTPS 反向代理',
        'systemd 托管',
        'logrotate 轮转',
        '平台管理员登录',
        '租户管理员登录',
        '新租户空库业务闭环',
        '创建项目',
        '录入收费对象',
        '配置收费项目',
        '生成账单',
        '登记收款',
        '查看欠费/实收报表',
        '导出账单或收款记录',
        '租户隔离验收',
        '客户上传数据与系统自身数据隔离',
        '授权绑定恢复',
        'system/license_bindings/tenant_license_bindings.json',
        '备份恢复演练',
        'scripts/saas_backup.sh',
        'scripts/saas_restore.sh --verify-metadata',
        'scripts/saas_release_gate.py',
        'release/saas-release-evidence.md',
        'release/saas-isolation-evidence.md',
        '失败即停止交付',
        '不包含业主端 H5、微信/支付宝真实支付',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_production_deployment_rehearsal_check_script_passes_and_release_gate_includes_it():
    assert SCRIPT.exists(), 'missing production deployment rehearsal check script'
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for text in [
        'PASS saas production deployment rehearsal doc',
        'PASS saas production deployment rehearsal page',
        'PASS saas production deployment rehearsal registry',
        'PASS saas production deployment rehearsal gate',
        'saas_production_deployment_rehearsal_check: PASS',
    ]:
        assert text in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_production_deployment_rehearsal_check.py' in gate


def test_deploy_checklist_shows_production_rehearsal_without_internal_fields_or_secrets():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '实机部署物业',
        'project_name': '实机部署项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200

    page = client.get('/backoffice/deploy-checklist')
    assert page.status_code == 200
    for text in [
        '实机部署演练',
        'docs/saas-production-deployment-rehearsal.md',
        'scripts/saas_production_deployment_rehearsal_check.py',
        '通用 Linux/VPS',
        '腾讯云 CVM',
        '阿里云 ECS',
        '平台管理员登录',
        '租户管理员登录',
        '新租户空库业务闭环',
        '租户隔离验收',
        '授权绑定恢复',
        '客户上传数据与系统自身数据隔离',
        '失败即停止交付',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
