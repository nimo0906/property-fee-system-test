#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check first tenant delivery flow links recommended fee initialization."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    wizard = (ROOT / 'server/saas_first_tenant_wizard_pages.py').read_text(encoding='utf-8')
    package = (ROOT / 'server/saas_first_tenant_delivery_package_pages.py').read_text(encoding='utf-8')
    for item in ['一键初始化推荐收费项目', '/backoffice/fee-types/init-from-template', '按业务模板生成推荐收费项目']:
        require(item in wizard, f'wizard missing fee init item: {item}')
    for item in ['推荐收费项目初始化', '/backoffice/fee-types/init-from-template', '按当前业务模板一键创建推荐收费项目']:
        require(item in package, f'package missing fee init item: {item}')
    for script in ['scripts/saas_first_tenant_delivery_loop_check.py', 'scripts/saas_first_tenant_delivery_package_check.py']:
        result = subprocess.run([sys.executable, script], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
        require(result.returncode == 0, result.stdout)
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        require(forbidden not in wizard + package, f'delivery flow leaks forbidden value: {forbidden}')
    require('scripts/saas_first_tenant_fee_init_delivery_check.py' in (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8'), 'release gate missing fee init delivery check')
    print('saas_first_tenant_fee_init_delivery_check: PASS')


if __name__ == '__main__':
    main()
