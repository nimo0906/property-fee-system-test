#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check first tenant acceptance fee type review checklist."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'server/saas_first_tenant_acceptance_pages.py'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    text = PAGE.read_text(encoding='utf-8')
    for item in [
        '金额配置复核', '推荐收费项目已初始化', '收费项目单价已按客户标准复核',
        '计费方式已确认', '业务模板与收费项目匹配', '首租户交付验收记录（打印版）',
        '/backoffice/first-tenant-acceptance/export.html',
    ]:
        require(item in text, f'missing acceptance fee review item: {item}')
    for script in ['scripts/saas_first_tenant_acceptance_record_check.py', 'scripts/saas_first_tenant_acceptance_export_check.py']:
        result = subprocess.run([sys.executable, script], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
        require(result.returncode == 0, result.stdout)
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(forbidden not in text, f'acceptance fee review leaks forbidden value: {forbidden}')
    require('scripts/saas_first_tenant_acceptance_fee_review_check.py' in (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8'), 'release gate missing acceptance fee review check')
    print('saas_first_tenant_acceptance_fee_review_check: PASS')


if __name__ == '__main__':
    main()
