#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check recommended fee type initialization from business template."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    helper = (ROOT / 'server/saas_fee_type_template_init.py').read_text(encoding='utf-8')
    page = (ROOT / 'server/saas_fee_type_pages.py').read_text(encoding='utf-8')
    for item in ['recommended_fee_rows', 'initialize_recommended_fee_types', 'fee_type.template_init']:
        require(item in helper, f'missing helper item: {item}')
    for item in ['模板推荐收费项目', '/backoffice/fee-types/init-from-template', '一键初始化推荐收费项目']:
        require(item in page, f'missing page item: {item}')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo']:
        require(forbidden not in helper + page, f'sensitive marker leaked: {forbidden}')
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/test_saas_fee_type_template_init_pages.py', '-q'],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False,
    )
    require(result.returncode == 0, result.stdout)
    require('scripts/saas_fee_type_template_init_check.py' in (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8'), 'release gate missing fee type template init check')
    print('saas_fee_type_template_init_check: PASS')


if __name__ == '__main__':
    main()
