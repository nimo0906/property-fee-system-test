#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check tenant business config management page."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    page = (ROOT / 'server/saas_tenant_business_config_pages.py').read_text(encoding='utf-8')
    registry = (ROOT / 'server/saas_page_registry.py').read_text(encoding='utf-8')
    home = (ROOT / 'server/saas_backoffice_pages.py').read_text(encoding='utf-8')
    for item in ['业务配置', '/backoffice/tenant-business-config', '当前业务模板', '隔离边界']:
        require(item in page + home, f'missing page item: {item}')
    require('register_tenant_business_config_pages' in registry, 'page not registered')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo']:
        require(forbidden not in page, f'sensitive marker leaked: {forbidden}')
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/test_saas_tenant_business_config_pages.py', '-q'],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False,
    )
    require(result.returncode == 0, result.stdout)
    require('scripts/saas_tenant_business_config_page_check.py' in (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8'), 'release gate missing business config page check')
    print('saas_tenant_business_config_page_check: PASS')


if __name__ == '__main__':
    main()
