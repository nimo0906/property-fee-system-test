#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check tenant business template assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    files = [
        ROOT / 'server/saas_business_templates.py',
        ROOT / 'server/saas_first_tenant_wizard_pages.py',
        ROOT / 'server/saas_import_pages.py',
    ]
    text = '\n'.join(path.read_text(encoding='utf-8') for path in files)
    for item in [
        '住宅物业', '商业/商铺', '园区/办公', '混合项目', '收费对象字段', '推荐收费项目',
        '账单周期', '导入样例', '住宅楼,1单元,101,居民,80', '商业区,一层,A-001,商户,56.5',
        '园区A,办公楼,501,办公,120', '混合区,商住楼,201,居民,90', 'business_template',
    ]:
        require(item in text, f'missing business template item: {item}')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(forbidden not in (ROOT / 'server/saas_business_templates.py').read_text(encoding='utf-8'), f'template leaks forbidden value: {forbidden}')
    require('scripts/saas_tenant_business_template_check.py' in (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8'), 'release gate missing business template check')
    print('saas_tenant_business_template_check: PASS')


if __name__ == '__main__':
    main()
