#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check license binding operations runbook asset."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-license-binding-ops-runbook.md'
GATE = ROOT / 'scripts/saas_release_gate.py'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    require(DOC.exists(), 'missing license binding ops runbook')
    text = DOC.read_text(encoding='utf-8')
    for item in [
        'SaaS 授权绑定运维交付清单', '授权绑定', '备份', '恢复', '迁移', '审计检查',
        'system/license_bindings/tenant_license_bindings.json', 'scripts/saas_license_tenant_binding_check.py',
        'scripts/saas_license_binding_page_check.py', 'scripts/saas_license_binding_persistence_check.py',
        'scripts/saas_license_binding_backup_check.py', '不得写入客户上传数据目录',
        '不得写入 SaaS 业务表', 'license.tenant_bind',
    ]:
        require(item in text, f'runbook missing: {item}')
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in text, f'runbook leaks forbidden value: {forbidden}')
    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_license_binding_runbook_check.py' in gate, 'release gate missing license binding runbook check')
    print('saas_license_binding_runbook_check: PASS')


if __name__ == '__main__':
    main()
