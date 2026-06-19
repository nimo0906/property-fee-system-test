#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check first tenant acceptance record page assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'server/saas_first_tenant_acceptance_pages.py'
REGISTRY = ROOT / 'server/saas_page_registry.py'
GATE = ROOT / 'scripts/saas_release_gate.py'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    text = PAGE.read_text(encoding='utf-8')
    for item in [
        '首租户交付验收记录', '客户公司已创建', '项目已创建', '管理员已创建', '授权已绑定',
        '导入模板已确认', '收费项目已配置', '推荐收费项目已初始化', '收费项目单价已按客户标准复核', '计费方式已确认', '业务模板与收费项目匹配', '金额配置复核', '测试账单已生成', '测试收款已登记', '报表已核对',
        '租户隔离已验收', '备份恢复已演练', '实施人员', '客户签收人', '保存验收记录',
        '客户上传数据与系统自身数据隔离', '/backoffice/first-tenant-acceptance',
    ]:
        require(item in text, f'missing acceptance record item: {item}')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(forbidden not in text, f'acceptance page leaks forbidden value: {forbidden}')
    registry = REGISTRY.read_text(encoding='utf-8')
    require('register_first_tenant_acceptance_pages' in registry, 'registry missing acceptance record page')
    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_first_tenant_acceptance_record_check.py' in gate, 'release gate missing acceptance record check')
    print('saas_first_tenant_acceptance_record_check: PASS')


if __name__ == '__main__':
    main()
