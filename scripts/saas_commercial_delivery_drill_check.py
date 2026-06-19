#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check commercial delivery drill assets and gate registration."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/saas-commercial-delivery-drill.md'
DRILL = ROOT / 'scripts/saas_commercial_delivery_drill.py'
PAGE = ROOT / 'server/saas_commercial_readiness.py'
GATE = ROOT / 'scripts/saas_release_gate.py'
PYTHON = sys.executable


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def require_text(path, items):
    text = path.read_text(encoding='utf-8')
    for item in items:
        require(item in text, f'missing {path}: {item}')
    return text


def main():
    require(DOC.exists(), 'missing commercial delivery drill doc')
    doc = require_text(DOC, [
        'SaaS 云端商业版交付演示手册', '新租户从空库开始', '创建项目',
        '导入/录入收费对象', '配置收费项目', '生成账单', '账单审核', '登记收款',
        '查看欠费/实收报表', '导出账单或收款记录', '备份和恢复演练', '租户数据隔离',
        '客户上传数据与系统自身数据隔离', '正式商业后台', 'scripts/saas_commercial_delivery_drill.py',
    ])
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in doc, f'doc leaks sensitive or local value: {forbidden}')
    print('PASS saas commercial delivery drill doc')

    require(DRILL.exists(), 'missing commercial delivery drill script')
    result = subprocess.run([PYTHON, str(DRILL)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
    require(result.returncode == 0, result.stdout)
    require('saas_commercial_delivery_drill: PASS' in result.stdout, 'drill script did not pass')
    print('PASS saas commercial delivery drill script')

    page = require_text(PAGE, [
        'P0-11 商业交付演示', '新租户从空库开始', 'docs/saas-commercial-delivery-drill.md',
        'scripts/saas_commercial_delivery_drill.py', 'scripts/saas_commercial_delivery_drill_check.py',
    ])
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(hidden not in page, f'page leaks internal field or secret name: {hidden}')
    print('PASS saas commercial delivery readiness page')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_commercial_delivery_drill.py' in gate, 'release gate missing delivery drill')
    require('scripts/saas_commercial_delivery_drill_check.py' in gate, 'release gate missing delivery drill check')
    print('PASS saas commercial delivery release gate')
    print('saas_commercial_delivery_drill_check: PASS')


if __name__ == '__main__':
    main()
