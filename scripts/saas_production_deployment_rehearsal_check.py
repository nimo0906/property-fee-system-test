#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production-like deployment rehearsal assets for SaaS release."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-production-deployment-rehearsal.md'
PAGE = ROOT / 'server/saas_deploy_pages.py'
DEPLOY = ROOT / 'server/saas_deploy.py'
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
    doc = require_text(DOC, [
        'SaaS 商业版实机部署演练验收清单', '通用 Linux/VPS', '腾讯云 CVM', '阿里云 ECS',
        'SSH 登录与基础环境', 'Docker Compose 启动', 'Nginx HTTPS 反向代理', 'systemd 托管',
        'logrotate 轮转', '平台管理员登录', '租户管理员登录', '新租户空库业务闭环',
        '创建项目', '录入收费对象', '配置收费项目', '生成账单', '登记收款',
        '查看欠费/实收报表', '导出账单或收款记录', '租户隔离验收',
        '客户上传数据与系统自身数据隔离', '授权绑定恢复',
        'system/license_bindings/tenant_license_bindings.json', '备份恢复演练',
        'scripts/saas_backup.sh', 'scripts/saas_restore.sh --verify-metadata',
        'scripts/saas_release_gate.py', 'release/saas-release-evidence.md',
        'release/saas-isolation-evidence.md', '失败即停止交付',
        '不包含业主端 H5、微信/支付宝真实支付',
    ])
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in doc, f'doc leaks forbidden value: {forbidden}')
    print('PASS saas production deployment rehearsal doc')

    page = require_text(PAGE, [
        '实机部署演练', 'docs/saas-production-deployment-rehearsal.md',
        'scripts/saas_production_deployment_rehearsal_check.py', '通用 Linux/VPS',
        '腾讯云 CVM', '阿里云 ECS', '平台管理员登录', '租户管理员登录',
        '新租户空库业务闭环', '租户隔离验收', '授权绑定恢复',
        '客户上传数据与系统自身数据隔离', '失败即停止交付',
    ])
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(forbidden not in page, f'page leaks internal field or secret name: {forbidden}')
    print('PASS saas production deployment rehearsal page')

    deploy = require_text(DEPLOY, [
        'docs/saas-production-deployment-rehearsal.md',
        'scripts/saas_production_deployment_rehearsal_check.py',
    ])
    require('REQUIRED_DEPLOY_FILES' in deploy, 'deployment registry missing required files tuple')
    print('PASS saas production deployment rehearsal registry')

    gate = require_text(GATE, ['scripts/saas_production_deployment_rehearsal_check.py'])
    require('CHECKS' in gate, 'release gate missing checks list')
    print('PASS saas production deployment rehearsal gate')
    print('saas_production_deployment_rehearsal_check: PASS')


if __name__ == '__main__':
    main()
