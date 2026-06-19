#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check first tenant post-onboarding delivery loop assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'server/saas_first_tenant_wizard_pages.py'
GATE = ROOT / 'scripts/saas_release_gate.py'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    text = PAGE.read_text(encoding='utf-8')
    for item in [
        '首租户业务引导闭环', '创建完成后会显示可点击的业务交付路径',
        '1. 导入收费对象模板', '2. 配置收费项目', '3. 生成首批测试账单',
        '4. 登记测试收款', '5. 查看欠费/实收报表', '6. 生成交付验收记录',
        '一键初始化推荐收费项目', '/backoffice/fee-types/init-from-template', '按业务模板生成推荐收费项目', '/backoffice/imports/templates/charge-targets', '/backoffice/imports', '/backoffice/fee-types',
        '/backoffice/bills', '/backoffice/payments', '/backoffice/reports', '/backoffice/acceptance',
        '租户隔离验收', '备份恢复演练', '客户上传数据与系统自身数据隔离',
    ]:
        require(item in text, f'missing delivery loop item: {item}')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        require(forbidden not in text, f'delivery loop leaks secret name: {forbidden}')
    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_first_tenant_delivery_loop_check.py' in gate, 'release gate missing first tenant delivery loop check')
    print('saas_first_tenant_delivery_loop_check: PASS')


if __name__ == '__main__':
    main()
