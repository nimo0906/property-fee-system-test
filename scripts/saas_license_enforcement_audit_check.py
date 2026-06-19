#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check license write-block audit events are tenant-scoped and sanitized."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_cloud import LicenseCloudService


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    app = create_app()
    app.state.license_service = LicenseCloudService.in_memory()
    client = TestClient(app)
    login = client.post('/api/auth/login', json={'tenant_name': '授权审计检查物业', 'project_name': '授权审计检查项目', 'username': 'admin', 'role_code': 'system_admin'})
    require(login.status_code == 200, 'login failed')
    denied = client.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5, 'billing_mode': 'area'})
    require(denied.status_code == 403, 'unlicensed write not blocked')
    logs = client.get('/api/audit-logs').json()['items']
    blocked = [item for item in logs if item['action'] == 'license.write_blocked']
    require(blocked, 'missing license.write_blocked audit')
    detail_text = str(blocked[-1].get('detail'))
    for item in ['fee_type.create', 'missing', 'blocked']:
        require(item in detail_text, f'audit detail missing: {item}')
    for forbidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'property_license_cloud', 'property_saas']:
        require(forbidden not in detail_text, f'audit leaks forbidden field: {forbidden}')
    gate = (ROOT / 'scripts/saas_release_gate.py').read_text(encoding='utf-8')
    require('scripts/saas_license_enforcement_audit_check.py' in gate, 'release gate missing license enforcement audit check')
    print('saas_license_enforcement_audit_check: PASS')


if __name__ == '__main__':
    main()
