#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial readiness dashboard for SaaS backoffice."""

from fastapi.testclient import TestClient

from server.saas_app import create_app


def test_acceptance_page_shows_commercial_readiness_sections_and_gates():
    client = TestClient(create_app())
    client.post('/api/auth/login', json={
        'tenant_name': '商业验收物业', 'project_name': '商业验收项目', 'username': 'admin', 'role_code': 'system_admin'
    })

    page = client.get('/backoffice/acceptance')

    assert page.status_code == 200
    for text in [
        '商业上线总览', 'P0-1 业主与收费对象', 'P0-2 计费规则', 'P0-3 批量出账',
        'P0-4 收款欠费', 'P0-5 收据导出', 'P0-6 导入复核', 'P0-7 高风险审计',
        'P0-8 备份恢复', '租户隔离证据', '商业上线总门禁', '上线证据报告',
        'scripts/saas_commercial_readiness_check.py'
    ]:
        assert text in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
