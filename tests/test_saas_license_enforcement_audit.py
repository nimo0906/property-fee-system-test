#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit license-based write blocking in SaaS backoffice."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_license_cloud import LicenseCloudService


def _login(client, tenant='授权审计物业'):
    return client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': '授权审计项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })


def test_unlicensed_write_block_is_audited_in_memory_service():
    app = create_app()
    app.state.license_service = LicenseCloudService.in_memory()
    client = TestClient(app)
    assert _login(client).status_code == 200

    denied = client.post('/api/fee-types', json={
        'name': '物业费',
        'unit_price': 2.5,
        'billing_mode': 'area',
    })

    assert denied.status_code == 403
    logs = client.get('/api/audit-logs').json()['items']
    blocked = [item for item in logs if item['action'] == 'license.write_blocked']
    assert blocked, logs
    detail = blocked[-1]['detail']
    assert detail['module'] == 'fee_type.create'
    assert detail['license_status'] == 'missing'
    assert detail['blocked'] is True
    assert 'tenant_id' not in str(detail)
    assert 'project_id' not in str(detail)
    assert 'POSTGRES_PASSWORD' not in str(detail)
    assert 'APP_SECRET_KEY' not in str(detail)


def test_license_block_audit_uses_existing_tenant_scope_only():
    app = create_app()
    app.state.license_service = LicenseCloudService.in_memory()
    client_a = TestClient(app)
    client_b = TestClient(app)
    assert _login(client_a, tenant='授权审计A物业').status_code == 200
    assert _login(client_b, tenant='授权审计B物业').status_code == 200

    assert client_a.post('/api/fee-types', json={'name': '物业费A', 'unit_price': 2.0}).status_code == 403
    assert client_b.post('/api/fee-types', json={'name': '物业费B', 'unit_price': 3.0}).status_code == 403

    logs_a = client_a.get('/api/audit-logs').json()['items']
    logs_b = client_b.get('/api/audit-logs').json()['items']
    assert all(item['tenant_name'] == '授权审计A物业' for item in logs_a)
    assert all(item['tenant_name'] == '授权审计B物业' for item in logs_b)
    assert any(item['action'] == 'license.write_blocked' for item in logs_a)
    assert any(item['action'] == 'license.write_blocked' for item in logs_b)


def test_license_enforcement_audit_check_script_is_in_release_gate():
    script = Path('scripts/saas_license_enforcement_audit_check.py')
    assert script.exists(), 'missing SaaS license enforcement audit check script'
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert 'saas_license_enforcement_audit_check: PASS' in result.stdout
    gate = Path('scripts/saas_release_gate.py').read_text(encoding='utf-8')
    assert 'scripts/saas_license_enforcement_audit_check.py' in gate
