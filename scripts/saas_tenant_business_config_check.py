#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check tenant business config persistence assets."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    module = (ROOT / 'server/saas_tenant_business_config.py').read_text(encoding='utf-8')
    require('system/tenant_business_configs/tenant_business_configs.json' in module, 'system config path missing')
    require('save_tenant_business_template' in module, 'save helper missing')
    require('business_template_for_user' in module, 'read helper missing')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY']:
        require(forbidden not in module, f'sensitive marker leaked: {forbidden}')
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/test_saas_tenant_business_config_persistence.py', '-q'],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False,
    )
    require(result.returncode == 0, result.stdout)
    require('scripts/saas_tenant_business_config_check.py' in (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8'), 'release gate missing tenant business config check')
    print('saas_tenant_business_config_check: PASS')


if __name__ == '__main__':
    main()
