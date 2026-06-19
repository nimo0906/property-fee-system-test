#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deployment drill readiness check for SaaS commercial cloud release."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-cloud-deployment-drill.md'
PAGE = ROOT / 'server/saas_deploy_pages.py'
GATE = ROOT / 'scripts/saas_release_gate.py'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def require_text(path, items):
    text = path.read_text(encoding='utf-8')
    for item in items:
        require(item in text, f'missing {path}: {item}')
    return text


def main():
    require(DOC.exists(), 'missing deployment drill doc')
    doc = require_text(DOC, [
        'SaaS 云端商业版部署演练手册', '通用 Linux/VPS', '腾讯云', '阿里云',
        '.env.example', '不提交真实 .env', 'docker compose up -d',
        'deploy/nginx/property-saas.conf', 'HTTPS', 'deploy/systemd/property-saas.service',
        'deploy/logrotate/property-saas', 'scripts/saas_backup.sh',
        'scripts/saas_restore.sh --verify-metadata', 'scripts/saas_release_gate.py',
        'scripts/saas_commercial_readiness_check.py', '客户上传数据与系统自身数据隔离',
        '租户数据隔离', '回退与故障处理', '暂不包含业主端 H5、微信/支付宝真实支付',
    ])
    for secret in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(secret not in doc, f'doc leaks sensitive or local value: {secret}')
    print('PASS saas deployment drill doc')

    for path in [
        'docker-compose.yml', '.env.example', 'deploy/nginx/property-saas.conf',
        'deploy/systemd/property-saas.service', 'deploy/logrotate/property-saas',
        'scripts/saas_backup.sh', 'scripts/saas_restore.sh',
    ]:
        require((ROOT / path).exists(), f'missing deployment asset: {path}')
    print('PASS saas deployment assets')

    page = require_text(PAGE, [
        '云端部署演练', '通用 Linux/VPS', '腾讯云', '阿里云',
        'docs/saas-cloud-deployment-drill.md', 'scripts/saas_deployment_drill_check.py',
        'scripts/saas_commercial_readiness_check.py', '客户上传数据与系统自身数据隔离',
        '暂不包含业主端 H5、微信/支付宝真实支付',
    ])
    for secret in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(secret not in page, f'page leaks internal field or secret name: {secret}')
    print('PASS saas deployment drill page')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_deployment_drill_check.py' in gate, 'release gate missing deployment drill check')
    print('PASS saas deployment drill gate')
    print('saas_deployment_drill_check: PASS')


if __name__ == '__main__':
    main()
