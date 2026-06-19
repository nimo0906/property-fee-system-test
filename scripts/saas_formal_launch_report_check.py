#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check formal DOCX/PDF launch report assets."""

from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / 'release/saas-commercial-launch-report.docx'
PDF = ROOT / 'release/saas-commercial-launch-report.pdf'
PAGE = ROOT / 'server/saas_commercial_readiness.py'
GATE = ROOT / 'scripts/saas_release_gate.py'

REQUIRED = [
    'SaaS 云端商业版上线总报告', '总体结论', 'P0-1 到 P0-13 完成状态',
    '验证命令', '部署资产', '演示路径', '签收路径', '租户数据隔离',
    '客户上传数据与系统自身数据隔离', '不包含业主端 H5、微信/支付宝真实支付',
]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def docx_xml(name):
    with zipfile.ZipFile(DOCX) as zf:
        return zf.read(name).decode('utf-8')


def main():
    require(DOCX.exists() and DOCX.stat().st_size > 10000, 'missing or too small formal launch report docx')
    text_xml = docx_xml('word/document.xml')
    flat = re.sub(r'<[^>]+>', '', text_xml)
    for item in REQUIRED:
        require(item in flat, f'docx missing item: {item}')
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        require(forbidden not in flat, f'docx leaks sensitive or local value: {forbidden}')
    print('PASS saas formal launch report docx')

    require(PDF.exists() and PDF.stat().st_size > 10000, 'missing or too small formal launch report pdf')
    print('PASS saas formal launch report pdf')

    styles = docx_xml('word/styles.xml')
    require('宋体' in styles, 'docx styles missing Songti font')
    require('w:line="192"' in text_xml or 'w:line="192"' in styles, 'docx missing 0.8 line spacing')
    require('w:firstLine="480"' in text_xml, 'docx missing two-character first-line indent')
    require('w:sz="24"' in styles or 'w:sz="24"' in text_xml, 'docx missing small-four body size')
    require('w:sz w:val="44"' in text_xml, 'docx missing title size 22pt')
    print('PASS saas formal launch report formatting')

    page = PAGE.read_text(encoding='utf-8')
    for item in [
        'P0-15 正式报告文件', 'release/saas-commercial-launch-report.docx',
        'release/saas-commercial-launch-report.pdf', 'scripts/saas_formal_launch_report_check.py',
    ]:
        require(item in page, f'page missing item: {item}')
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        require(hidden not in page, f'page leaks internal field or secret name: {hidden}')
    print('PASS saas formal launch report page')

    gate = GATE.read_text(encoding='utf-8')
    require('scripts/saas_formal_launch_report_check.py' in gate, 'release gate missing formal launch report check')
    print('PASS saas formal launch report release gate')
    print('saas_formal_launch_report_check: PASS')


if __name__ == '__main__':
    main()
