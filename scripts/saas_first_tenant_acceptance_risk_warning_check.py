#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check first tenant acceptance risk warning."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'server/saas_first_tenant_acceptance_pages.py'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    text = PAGE.read_text(encoding='utf-8')
    for item in [
        '验收风险', '验收风险已解除', '完成项不足', '金额配置复核未完成',
        '上线前请勿签收', 'FEE_REVIEW_ITEMS', '_risk_summary', '_risk_panel', '风险状态', '风险说明',
    ]:
        require(item in text, f'missing acceptance risk warning item: {item}')
    for forbidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(forbidden not in text, f'acceptance risk warning leaks forbidden value: {forbidden}')
    require('scripts/saas_first_tenant_acceptance_risk_warning_check.py' in (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8'), 'release gate missing acceptance risk warning check')
    print('saas_first_tenant_acceptance_risk_warning_check: PASS')


if __name__ == '__main__':
    main()
