#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check next phase executable issue backlog assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-next-phase-issue-backlog.md'
PAGE = ROOT / 'server/saas_commercial_readiness.py'
GATE = ROOT / 'scripts/saas_release_gate.py'

REQUIRED_ASSETS = [
    'docs/saas-next-phase-issue-backlog.md',
    'docs/saas-next-phase-decision-checklist.md',
    'docs/saas-day7-stability-review.md',
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
    require(DOC.exists(), 'missing next phase issue backlog')
    doc = require_text(DOC, [
        'SaaS 云端商业版下一阶段可执行工单清单', '工单拆分原则',
        '业主端 H5 工单包', '支付工单包', '授权云服务后台工单包', '桌面版存量业务迁移工单包',
        'ISSUE-H5-01', 'ISSUE-PAY-01', 'ISSUE-LIC-01', 'ISSUE-MIG-01',
        '验收口径', '依赖关系', '风险边界', '不得与 SaaS 业务主库混用',
        '不得破坏租户数据隔离', '不得把客户上传数据与系统自身数据混在一起',
        'docs/saas-next-phase-decision-checklist.md', 'docs/saas-day7-stability-review.md',
    ])
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in doc, f'next phase issue backlog leaks sensitive or local value: {forbidden}')
    print('PASS saas next phase issue backlog doc')

    for path in REQUIRED_ASSETS:
        require((ROOT / path).exists(), f'missing next phase issue backlog asset: {path}')
    print('PASS saas next phase issue backlog assets')

    page = require_text(PAGE, [
        'P0-20 下一阶段工单清单', 'docs/saas-next-phase-issue-backlog.md',
        'scripts/saas_next_phase_issue_backlog_check.py', '业主端 H5 工单包', '支付工单包',
    ])
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(hidden not in page, f'page leaks internal field or secret name: {hidden}')
    print('PASS saas next phase issue backlog page')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_next_phase_issue_backlog_check.py' in gate, 'release gate missing next phase issue backlog check')
    print('PASS saas next phase issue backlog release gate')
    print('saas_next_phase_issue_backlog_check: PASS')


if __name__ == '__main__':
    main()
