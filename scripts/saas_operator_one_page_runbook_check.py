#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check one-page operator launch runbook assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-operator-one-page-runbook.md'
PAGE = ROOT / 'server/saas_commercial_readiness.py'
GATE = ROOT / 'scripts/saas_release_gate.py'

REQUIRED_ASSETS = [
    'docs/saas-operator-one-page-runbook.md',
    'scripts/saas_release_gate.py',
    'scripts/saas_commercial_delivery_drill.py',
    'scripts/saas_backup.sh',
    'scripts/saas_restore.sh',
    'release/saas-commercial-launch-report.pdf',
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
    require(DOC.exists(), 'missing operator one-page runbook')
    doc = require_text(DOC, [
        'SaaS 云端商业版实施人员一页式上线操作指引', '执行顺序', '1. 准备服务器',
        '2. 配置环境变量', '3. 启动服务', '4. 运行上线门禁', '5. 执行业务演示',
        '6. 执行备份恢复演练', '7. 核对租户隔离', '8. 完成客户签收',
        '9. 留存上线报告', '10. 回退条件', 'docker compose up -d',
        'scripts/saas_release_gate.py', 'scripts/saas_commercial_delivery_drill.py',
        'scripts/saas_backup.sh', 'scripts/saas_restore.sh --verify-metadata',
        'release/saas-commercial-launch-report.pdf', 'docs/saas-customer-acceptance-signoff.md',
        '客户上传数据与系统自身数据隔离', '租户数据隔离', '不提交真实 .env',
    ])
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in doc, f'runbook leaks sensitive or local value: {forbidden}')
    print('PASS saas operator one-page runbook doc')

    for path in REQUIRED_ASSETS:
        require((ROOT / path).exists(), f'missing operator runbook asset: {path}')
    print('PASS saas operator one-page runbook assets')

    page = require_text(PAGE, [
        'P0-16 一页式上线指引', 'docs/saas-operator-one-page-runbook.md',
        'scripts/saas_operator_one_page_runbook_check.py', '执行顺序',
    ])
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(hidden not in page, f'page leaks internal field or secret name: {hidden}')
    print('PASS saas operator one-page runbook page')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_operator_one_page_runbook_check.py' in gate, 'release gate missing operator runbook check')
    print('PASS saas operator one-page runbook release gate')
    print('saas_operator_one_page_runbook_check: PASS')


if __name__ == '__main__':
    main()
