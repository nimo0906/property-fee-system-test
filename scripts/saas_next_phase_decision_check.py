#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check next phase decision checklist assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-next-phase-decision-checklist.md'
PAGE = ROOT / 'server/saas_commercial_readiness.py'
GATE = ROOT / 'scripts/saas_release_gate.py'

REQUIRED_ASSETS = [
    'docs/saas-next-phase-decision-checklist.md',
    'docs/saas-day7-stability-review.md',
    'release/saas-commercial-launch-report.pdf',
    'scripts/saas_release_gate.py',
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
    require(DOC.exists(), 'missing next phase decision checklist')
    doc = require_text(DOC, [
        'SaaS 云端商业版下一阶段立项决策清单', '立项前置条件', '候选方向',
        '业主端 H5', '微信/支付宝真实支付', '授权云服务后台', '更多桌面版存量业务迁移',
        '优先级建议', '进入条件', '不进入条件', '风险和边界',
        '不得与 SaaS 业务主库混用', '不得破坏租户数据隔离', '不得把客户上传数据与系统自身数据混在一起',
        'docs/saas-day7-stability-review.md', 'release/saas-commercial-launch-report.pdf',
        'scripts/saas_release_gate.py',
    ])
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in doc, f'next phase checklist leaks sensitive or local value: {forbidden}')
    print('PASS saas next phase decision checklist doc')

    for path in REQUIRED_ASSETS:
        require((ROOT / path).exists(), f'missing next phase decision asset: {path}')
    print('PASS saas next phase decision checklist assets')

    page = require_text(PAGE, [
        'P0-19 下一阶段立项决策', 'docs/saas-next-phase-decision-checklist.md',
        'scripts/saas_next_phase_decision_check.py', '业主端 H5', '微信/支付宝真实支付',
    ])
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(hidden not in page, f'page leaks internal field or secret name: {hidden}')
    print('PASS saas next phase decision checklist page')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_next_phase_decision_check.py' in gate, 'release gate missing next phase decision check')
    print('PASS saas next phase decision checklist release gate')
    print('saas_next_phase_decision_check: PASS')


if __name__ == '__main__':
    main()
