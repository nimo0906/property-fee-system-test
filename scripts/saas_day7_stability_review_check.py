#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check day-7 stability review assets for SaaS launch."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-day7-stability-review.md'
PAGE = ROOT / 'server/saas_commercial_readiness.py'
GATE = ROOT / 'scripts/saas_release_gate.py'

REQUIRED_ASSETS = [
    'docs/saas-day7-stability-review.md',
    'docs/saas-day1-operations-checklist.md',
    'release/saas-release-evidence.md',
    'release/saas-isolation-evidence.md',
    'docs/saas-customer-acceptance-signoff.md',
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
    require(DOC.exists(), 'missing day-7 stability review')
    doc = require_text(DOC, [
        'SaaS 云端商业版上线后 7 日稳定运行复盘清单', '复盘范围', '业务数据复盘',
        '金额报表复盘', '租户隔离复盘', '权限审计复盘', '备份恢复复盘',
        '日志和审计复盘', '客户反馈复盘', '遗留事项', '是否进入下一阶段',
        '业主端 H5', '微信/支付宝真实支付', '授权云服务后台',
        'release/saas-release-evidence.md', 'release/saas-isolation-evidence.md',
        'docs/saas-day1-operations-checklist.md', '客户上传数据与系统自身数据隔离', '租户数据隔离',
    ])
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in doc, f'day7 review leaks sensitive or local value: {forbidden}')
    print('PASS saas day7 stability review doc')

    for path in REQUIRED_ASSETS:
        require((ROOT / path).exists(), f'missing day7 review asset: {path}')
    print('PASS saas day7 stability review assets')

    page = require_text(PAGE, [
        'P0-18 七日稳定复盘', 'docs/saas-day7-stability-review.md',
        'scripts/saas_day7_stability_review_check.py', '是否进入下一阶段',
    ])
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(hidden not in page, f'page leaks internal field or secret name: {hidden}')
    print('PASS saas day7 stability review page')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_day7_stability_review_check.py' in gate, 'release gate missing day7 review check')
    print('PASS saas day7 stability review release gate')
    print('saas_day7_stability_review_check: PASS')


if __name__ == '__main__':
    main()
