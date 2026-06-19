#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check printable/exportable first tenant acceptance record assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'server/saas_first_tenant_acceptance_pages.py'
GATE = ROOT / 'scripts/saas_release_gate.py'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    text = PAGE.read_text(encoding='utf-8')
    for item in [
        '首租户交付验收记录（打印版）', '/backoffice/first-tenant-acceptance/print',
        '/backoffice/first-tenant-acceptance/export.html', '打印验收记录', '导出 HTML 验收记录',
        '客户签字', '实施人员签字', '签收日期', '@media print', 'window.print',
        'first-tenant-acceptance.html', '客户上传数据与系统自身数据隔离',
    ]:
        require(item in text, f'missing acceptance export item: {item}')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(forbidden not in text, f'acceptance export leaks forbidden value: {forbidden}')
    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_first_tenant_acceptance_export_check.py' in gate, 'release gate missing acceptance export check')
    print('saas_first_tenant_acceptance_export_check: PASS')


if __name__ == '__main__':
    main()
