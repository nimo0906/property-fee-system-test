#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production delivery missing evidence details."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.saas_app import create_app
from server.saas_production_delivery_pages import delivery_status_summary
import server.saas_production_delivery_pages as delivery_pages

SCRIPT = 'scripts/saas_production_delivery_missing_evidence_details_check.py'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        labels = [item['label'] for item in delivery_status_summary(root)['blockers']]
        for label in ['缺少生产验收留档', '缺少上线证据报告', '缺少租户隔离证据', '缺少签收历史']:
            require(label in labels, f'missing blocker: {label}')
        require('验收证据未补齐' not in labels, 'generic evidence blocker should be detailed')
        delivery_pages.ROOT = root
        client = TestClient(create_app())
        login = client.post('/api/auth/login', json={
            'tenant_name': '交付明细检查物业', 'project_name': '交付明细检查项目',
            'username': 'admin', 'role_code': 'system_admin',
        })
        require(login.status_code == 200, 'login failed')
        page = client.get('/backoffice/production-delivery')
        for label in labels:
            require(label in page.text, f'missing page label: {label}')
        require('验收证据未补齐</td>' not in page.text, 'generic blocker shown on page')
        for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', '/Users/nimo', 'tenant_id', 'project_id', '.env']:
            require(hidden not in page.text, f'forbidden page content: {hidden}')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py', 'server/saas_commercial_readiness.py']:
        require(SCRIPT in (ROOT / path).read_text(encoding='utf-8'), f'missing registry in {path}')
    print('saas_production_delivery_missing_evidence_details_check: PASS')


if __name__ == '__main__':
    main()
