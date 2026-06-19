#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check visual login and first tenant wizard assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def require_text(path, items):
    text = path.read_text(encoding='utf-8')
    for item in items:
        require(item in text, f'missing {path}: {item}')
    return text


def main():
    login = require_text(ROOT / 'server/saas_login_pages.py', [
        '物业收费管理系统 SaaS', '商业版员工后台登录', '客户公司', '项目名称',
        '登录账号', '角色', '进入员工后台', '客户数据隔离', '系统自身数据隔离',
        'action="/login"', 'method="post"', 'set_cookie', 'session_id',
    ])
    wizard = require_text(ROOT / 'server/saas_first_tenant_wizard_pages.py', [
        '客户首租户初始化向导', '创建客户公司', '创建默认项目', '创建租户管理员',
        '绑定授权客户编号', '导入收费对象模板', '配置收费项目', '生成首批测试账单',
        '登记测试收款', '验收租户隔离', '执行备份恢复演练', '客户上传数据与系统自身数据隔离',
        '业务数据不进入授权云服务', 'bind_tenant_license_customer',
    ])
    registry = require_text(ROOT / 'server/saas_page_registry.py', [
        'register_login_pages', 'register_first_tenant_wizard_pages',
    ])
    gate = require_text(ROOT / 'scripts/saas_release_gate.py', ['scripts/saas_first_tenant_wizard_check.py'])
    for text, name in [(login, 'login'), (wizard, 'wizard')]:
        for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
            require(forbidden not in text, f'{name} leaks secret name: {forbidden}')
    print('saas_first_tenant_wizard_check: PASS')


if __name__ == '__main__':
    main()
