#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check customer acceptance sign-off assets for SaaS launch."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-customer-acceptance-signoff.md'
READINESS_PAGE = ROOT / 'server/saas_commercial_readiness.py'
GATE = ROOT / 'scripts/saas_release_gate.py'

REQUIRED_ASSETS = [
    'docs/saas-customer-acceptance-signoff.md',
    'docs/saas-minimal-launch-package.md',
    'scripts/saas_release_gate.py',
    'scripts/saas_minimal_launch_package_check.py',
    'release/saas-release-evidence.md',
    'release/saas-isolation-evidence.md',
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
    require(DOC.exists(), 'missing customer acceptance signoff document')
    doc = require_text(DOC, [
        'SaaS 云端商业版上线前人工验收与客户交付签收清单', '客户信息', '部署完成确认',
        '最小上线包确认', '商业交付演示通过', '备份恢复演练通过', '租户隔离通过',
        '账号权限确认', '客户上传数据与系统自身数据隔离确认', '数据不混用确认',
        '上线证据确认', '问题与遗留事项', '客户签收', '实施人员签收',
        'scripts/saas_release_gate.py', 'scripts/saas_minimal_launch_package_check.py',
        'release/saas-release-evidence.md', 'release/saas-isolation-evidence.md', '不提交真实 .env',
    ])
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in doc, f'signoff doc leaks sensitive or local value: {forbidden}')
    print('PASS saas customer acceptance signoff doc')

    for path in REQUIRED_ASSETS:
        require((ROOT / path).exists(), f'missing customer signoff asset: {path}')
    print('PASS saas customer acceptance signoff assets')

    page = require_text(READINESS_PAGE, [
        'P0-13 客户交付签收', '上线前人工验收', 'docs/saas-customer-acceptance-signoff.md',
        'scripts/saas_customer_acceptance_signoff_check.py', '部署完成确认', '数据不混用确认',
    ])
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(hidden not in page, f'page leaks internal field or secret name: {hidden}')
    print('PASS saas customer acceptance signoff page')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_customer_acceptance_signoff_check.py' in gate, 'release gate missing customer signoff check')
    print('PASS saas customer acceptance signoff release gate')
    print('saas_customer_acceptance_signoff_check: PASS')


if __name__ == '__main__':
    main()
