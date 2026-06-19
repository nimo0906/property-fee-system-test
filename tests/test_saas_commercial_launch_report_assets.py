#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial launch summary report assets for SaaS cloud backoffice."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_commercial_launch_report_summarizes_p0_1_to_p0_13_and_delivery_evidence():
    doc = Path('docs/saas-commercial-launch-report.md')
    assert doc.exists(), 'missing commercial launch report'
    text = doc.read_text(encoding='utf-8')
    required = [
        'SaaS 云端商业版上线总报告',
        '总体结论',
        'P0-1 业主与收费对象',
        'P0-2 计费规则',
        'P0-3 批量出账',
        'P0-4 收款欠费',
        'P0-5 收据导出',
        'P0-6 导入复核',
        'P0-7 高风险审计',
        'P0-8 备份恢复',
        'P0-9 商业上线验收总览',
        'P0-10 云端部署演练',
        'P0-11 商业交付演示',
        'P0-12 最小上线包',
        'P0-13 客户交付签收',
        '验证命令',
        '部署资产',
        '演示路径',
        '签收路径',
        '租户数据隔离',
        '客户上传数据与系统自身数据隔离',
        'scripts/saas_release_gate.py',
        'scripts/saas_commercial_delivery_drill.py',
        'docs/saas-customer-acceptance-signoff.md',
        'release/saas-release-evidence.md',
        'release/saas-isolation-evidence.md',
        '不包含业主端 H5、微信/支付宝真实支付',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_commercial_launch_report_check_script_passes_and_release_gate_includes_it():
    script = Path('scripts/saas_commercial_launch_report_check.py')
    assert script.exists(), 'missing commercial launch report check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for text in [
        'PASS saas commercial launch report doc',
        'PASS saas commercial launch report assets',
        'PASS saas commercial launch report page',
        'PASS saas commercial launch report release gate',
        'saas_commercial_launch_report_check: PASS',
    ]:
        assert text in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_commercial_launch_report_check.py' in gate


def test_acceptance_page_shows_commercial_launch_report_without_internal_fields():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '上线报告物业',
        'project_name': '上线报告项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    for text in [
        'P0-14 上线总报告',
        'SaaS 云端商业版上线总报告',
        'docs/saas-commercial-launch-report.md',
        'scripts/saas_commercial_launch_report_check.py',
        'P0-1 到 P0-13',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
