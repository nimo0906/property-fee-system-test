#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check the minimal launch package for SaaS commercial cloud delivery."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-minimal-launch-package.md'
DEPLOY_PAGE = ROOT / 'server/saas_deploy_pages.py'
READINESS_PAGE = ROOT / 'server/saas_commercial_readiness.py'
GATE = ROOT / 'scripts/saas_release_gate.py'

REQUIRED_ASSETS = [
    'docker-compose.yml', '.env.example', 'deploy/nginx/property-saas.conf',
    'deploy/systemd/property-saas.service', 'deploy/logrotate/property-saas',
    'scripts/saas_release_gate.py', 'scripts/saas_commercial_delivery_drill.py',
    'scripts/saas_commercial_delivery_drill_check.py', 'scripts/saas_deployment_drill_check.py',
    'scripts/saas_backup.sh', 'scripts/saas_restore.sh', 'docs/saas-cloud-deployment-drill.md',
    'docs/saas-commercial-delivery-drill.md', 'release/saas-release-evidence.md',
]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def require_text(path, items):
    text = path.read_text(encoding='utf-8')
    for item in items:
        require(item in text, f'missing {path}: {item}')
    return text


def main():
    require(DOC.exists(), 'missing minimal launch package manifest')
    doc = require_text(DOC, [
        'SaaS 云端商业版最小上线包清单', '上线包范围', '部署配置', '运行服务',
        '数据隔离', '验收演示', '运维备份', '上线证据', 'docker-compose.yml',
        '.env.example', 'deploy/nginx/property-saas.conf', 'deploy/systemd/property-saas.service',
        'deploy/logrotate/property-saas', 'scripts/saas_release_gate.py',
        'scripts/saas_commercial_delivery_drill.py', 'scripts/saas_commercial_delivery_drill_check.py',
        'scripts/saas_deployment_drill_check.py', 'scripts/saas_backup.sh', 'scripts/saas_restore.sh',
        'docs/saas-cloud-deployment-drill.md', 'docs/saas-commercial-delivery-drill.md',
        'release/saas-release-evidence.md', '不提交真实 .env', '不包含业主端 H5、微信/支付宝真实支付',
        '客户上传数据与系统自身数据隔离', '租户数据隔离',
    ])
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in doc, f'manifest leaks sensitive or local value: {forbidden}')
    print('PASS saas minimal launch package manifest')

    for path in REQUIRED_ASSETS:
        require((ROOT / path).exists(), f'missing launch package asset: {path}')
    print('PASS saas minimal launch package assets')

    for page in [DEPLOY_PAGE, READINESS_PAGE]:
        text = require_text(page, [
            '最小上线包', 'docs/saas-minimal-launch-package.md',
            'scripts/saas_minimal_launch_package_check.py', '不提交真实 .env',
            '客户上传数据与系统自身数据隔离',
        ])
        for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
            require(hidden not in text, f'page leaks internal field or secret name: {hidden}')
    print('PASS saas minimal launch package pages')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_minimal_launch_package_check.py' in gate, 'release gate missing minimal launch package check')
    print('PASS saas minimal launch package release gate')
    print('saas_minimal_launch_package_check: PASS')


if __name__ == '__main__':
    main()
