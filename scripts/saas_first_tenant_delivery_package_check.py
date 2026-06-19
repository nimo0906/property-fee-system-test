#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check first tenant delivery package overview assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'server/saas_first_tenant_delivery_package_pages.py'
REGISTRY = ROOT / 'server/saas_page_registry.py'
HOME = ROOT / 'server/saas_backoffice_pages.py'
GATE = ROOT / 'scripts/saas_release_gate.py'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    text = PAGE.read_text(encoding='utf-8')
    for item in [
        '首租户交付包总览', '实施人员统一入口', '登录入口', '客户首租户初始化向导',
        '首租户业务引导闭环', '推荐收费项目初始化', '首租户交付验收记录', '验收记录打印版', 'HTML 导出',
        '生产部署一键自检', '备份恢复演练', '授权绑定', '租户隔离证据',
        '客户上传数据与系统自身数据隔离', '/login', '/backoffice/first-tenant-wizard',
        '/backoffice/first-tenant-acceptance', '/backoffice/first-tenant-acceptance/print',
        '/backoffice/first-tenant-acceptance/export.html', '/backoffice/deploy-checklist',
        '/backoffice/backups', '/backoffice/license-ops', '/backoffice/data-boundaries',
    ]:
        require(item in text, f'missing delivery package item: {item}')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(forbidden not in text, f'delivery package leaks forbidden value: {forbidden}')
    require('register_first_tenant_delivery_package_pages' in REGISTRY.read_text(encoding='utf-8'), 'registry missing delivery package page')
    require('/backoffice/first-tenant-delivery-package' in HOME.read_text(encoding='utf-8'), 'home missing delivery package link')
    require('scripts/saas_first_tenant_delivery_package_check.py' in GATE.read_text(encoding='utf-8'), 'release gate missing delivery package check')
    print('saas_first_tenant_delivery_package_check: PASS')


if __name__ == '__main__':
    main()
