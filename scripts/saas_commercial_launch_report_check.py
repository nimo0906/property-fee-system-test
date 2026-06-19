#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check commercial launch summary report assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-commercial-launch-report.md'
READINESS_PAGE = ROOT / 'server/saas_commercial_readiness.py'
GATE = ROOT / 'scripts/saas_release_gate.py'

REQUIRED_ASSETS = [
    'docs/saas-commercial-launch-report.md', 'docs/saas-customer-acceptance-signoff.md',
    'docs/saas-minimal-launch-package.md', 'docs/saas-cloud-deployment-drill.md',
    'scripts/saas_release_gate.py', 'scripts/saas_commercial_delivery_drill.py',
    'release/saas-release-evidence.md', 'release/saas-isolation-evidence.md',
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
    require(DOC.exists(), 'missing commercial launch report')
    doc = require_text(DOC, [
        'SaaS 云端商业版上线总报告', '总体结论', 'P0-1 业主与收费对象',
        'P0-2 计费规则', 'P0-3 批量出账', 'P0-4 收款欠费', 'P0-5 收据导出',
        'P0-6 导入复核', 'P0-7 高风险审计', 'P0-8 备份恢复',
        'P0-9 商业上线验收总览', 'P0-10 云端部署演练', 'P0-11 商业交付演示',
        'P0-12 最小上线包', 'P0-13 客户交付签收', '验证命令', '部署资产',
        '演示路径', '签收路径', '租户数据隔离', '客户上传数据与系统自身数据隔离',
        'scripts/saas_release_gate.py', 'scripts/saas_commercial_delivery_drill.py',
        'docs/saas-customer-acceptance-signoff.md', 'release/saas-release-evidence.md',
        'release/saas-isolation-evidence.md', '不包含业主端 H5、微信/支付宝真实支付',
    ])
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in doc, f'launch report leaks sensitive or local value: {forbidden}')
    print('PASS saas commercial launch report doc')

    for path in REQUIRED_ASSETS:
        require((ROOT / path).exists(), f'missing launch report asset: {path}')
    print('PASS saas commercial launch report assets')

    page = require_text(READINESS_PAGE, [
        'P0-14 上线总报告', 'SaaS 云端商业版上线总报告',
        'docs/saas-commercial-launch-report.md', 'scripts/saas_commercial_launch_report_check.py',
        'P0-1 到 P0-13',
    ])
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(hidden not in page, f'page leaks internal field or secret name: {hidden}')
    print('PASS saas commercial launch report page')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_commercial_launch_report_check.py' in gate, 'release gate missing launch report check')
    print('PASS saas commercial launch report release gate')
    print('saas_commercial_launch_report_check: PASS')


if __name__ == '__main__':
    main()
