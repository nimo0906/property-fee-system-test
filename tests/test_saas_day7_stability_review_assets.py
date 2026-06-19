#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Day-7 stability review assets for SaaS commercial launch."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_day7_stability_review_covers_week_one_business_and_ops_review():
    doc = Path('docs/saas-day7-stability-review.md')
    assert doc.exists(), 'missing day-7 stability review'
    text = doc.read_text(encoding='utf-8')
    required = [
        'SaaS 云端商业版上线后 7 日稳定运行复盘清单',
        '复盘范围',
        '业务数据复盘',
        '金额报表复盘',
        '租户隔离复盘',
        '权限审计复盘',
        '备份恢复复盘',
        '日志和审计复盘',
        '客户反馈复盘',
        '遗留事项',
        '是否进入下一阶段',
        '业主端 H5',
        '微信/支付宝真实支付',
        '授权云服务后台',
        'release/saas-release-evidence.md',
        'release/saas-isolation-evidence.md',
        'docs/saas-day1-operations-checklist.md',
        '客户上传数据与系统自身数据隔离',
        '租户数据隔离',
    ]
    for item in required:
        assert item in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '真实密码', '/Users/nimo']:
        assert forbidden not in text


def test_day7_stability_review_check_script_passes_and_release_gate_includes_it():
    script = Path('scripts/saas_day7_stability_review_check.py')
    assert script.exists(), 'missing day-7 stability review check script'
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
        'PASS saas day7 stability review doc',
        'PASS saas day7 stability review assets',
        'PASS saas day7 stability review page',
        'PASS saas day7 stability review release gate',
        'saas_day7_stability_review_check: PASS',
    ]:
        assert text in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_day7_stability_review_check.py' in gate


def test_acceptance_page_shows_day7_stability_review_without_internal_fields():
    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '七日复盘物业',
        'project_name': '七日复盘项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/acceptance')
    assert page.status_code == 200
    for text in [
        'P0-18 七日稳定复盘',
        'docs/saas-day7-stability-review.md',
        'scripts/saas_day7_stability_review_check.py',
        '是否进入下一阶段',
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
