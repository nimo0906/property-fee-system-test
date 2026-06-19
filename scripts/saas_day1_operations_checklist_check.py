#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check day-1 operations checklist assets for SaaS launch."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-day1-operations-checklist.md'
PAGE = ROOT / 'server/saas_commercial_readiness.py'
GATE = ROOT / 'scripts/saas_release_gate.py'

REQUIRED_ASSETS = [
    'docs/saas-day1-operations-checklist.md',
    'scripts/saas_release_gate.py',
    'scripts/saas_backup.sh',
    'scripts/saas_restore.sh',
    'release/saas-isolation-evidence.md',
    'release/saas-release-evidence.md',
]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def require_text(path, items):
    text = path.read_text(encoding='utf-8')
    for item in items:
        require(item in text, f'missing {path}: {item}')
    return text


def main():
    require(DOC.exists(), 'missing day-1 operations checklist')
    doc = require_text(DOC, [
        'SaaS 云端商业版上线后首日巡检清单', '巡检时间点', 'T+0 小时', 'T+2 小时',
        'T+24 小时', '服务健康', '登录和权限', '租户隔离', '出账/收款抽查',
        '备份检查', '日志检查', '审计检查', '报表核对', '客户上传数据与系统自身数据隔离',
        '回退观察点', 'scripts/saas_release_gate.py', 'scripts/saas_backup.sh',
        'release/saas-isolation-evidence.md', 'release/saas-release-evidence.md', '不得上线或必须回退',
    ])
    require('scripts/saas_restore.sh --verify-metadata' in doc, 'missing restore verify command')
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in doc, f'day1 checklist leaks sensitive or local value: {forbidden}')
    print('PASS saas day1 operations checklist doc')

    for path in REQUIRED_ASSETS:
        require((ROOT / path).exists(), f'missing day1 checklist asset: {path}')
    print('PASS saas day1 operations checklist assets')

    page = require_text(PAGE, [
        'P0-17 首日巡检清单', 'docs/saas-day1-operations-checklist.md',
        'scripts/saas_day1_operations_checklist_check.py', '服务健康', '回退观察点',
    ])
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(hidden not in page, f'page leaks internal field or secret name: {hidden}')
    print('PASS saas day1 operations checklist page')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_day1_operations_checklist_check.py' in gate, 'release gate missing day1 checklist check')
    print('PASS saas day1 operations checklist release gate')
    print('saas_day1_operations_checklist_check: PASS')


if __name__ == '__main__':
    main()
