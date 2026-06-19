#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extra boundary checks for SaaS acceptance script."""

from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_storage import SaasStorage


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def _login(client, tenant, project, username, role_code):
    response = client.post('/api/auth/login', json={
        'tenant_name': tenant,
        'project_name': project,
        'username': username,
        'role_code': role_code,
    })
    expect(response.status_code == 200, f'login failed for {username}: {response.text}')


def run_isolation_acceptance(label, database_url=None):
    app = create_app(database_url=database_url)
    client_a = TestClient(app)
    client_b = TestClient(app)
    _login(client_a, f'A验收物业-{label}', f'A验收项目-{label}', 'admin_a', 'system_admin')
    _login(client_b, f'B验收物业-{label}', f'B验收项目-{label}', 'admin_b', 'system_admin')
    target_a = client_a.post('/api/charge-targets', json={
        'building': 'A栋', 'unit': '1单元', 'room_number': '101', 'category': '居民', 'area': 80,
    }).json()['item']
    fee_b = client_b.post('/api/fee-types', json={'name': '物业费', 'unit_price': 2.5}).json()['item']
    cross_bill = client_b.post('/api/bills/generate', json={
        'target_id': target_a['id'], 'fee_type_id': fee_b['id'],
        'billing_period': '2026-06', 'service_start': '2026-06-01', 'service_end': '2026-06-30',
    })
    expect(cross_bill.status_code in {403, 404}, 'cross-tenant bill generation was allowed')
    expect(client_b.get('/api/charge-targets').json()['items'] == [], 'tenant B can list tenant A targets')
    b_logs = client_b.get('/api/audit-logs').json()['items']
    expect('A栋' not in str(b_logs), 'tenant B can read tenant A audit log detail')
    expect('charge_target.create' not in [row['action'] for row in b_logs], 'tenant B can read tenant A audit action')
    print(f'PASS saas acceptance isolation {label}')


def run_account_boundary_acceptance(label, database_url=None):
    app = create_app(database_url=database_url)
    platform = TestClient(app)
    tenant_a = TestClient(app)
    tenant_b = TestClient(app)
    _login(platform, f'平台验收-{label}', f'平台项目-{label}', 'platform_admin', 'platform_admin')
    _login(tenant_a, f'A账号物业-{label}', f'A账号项目-{label}', 'admin_a', 'system_admin')
    _login(tenant_b, f'B账号物业-{label}', f'B账号项目-{label}', 'admin_b', 'system_admin')
    blocked_create = platform.post('/api/users', json={'username': 'wrong_customer_staff', 'role_code': 'cashier'})
    expect(blocked_create.status_code == 403, 'platform admin directly created customer staff')
    created_b = tenant_b.post('/api/users', json={'username': 'b_cashier', 'role_code': 'cashier'})
    expect(created_b.status_code == 200, f'tenant B user create failed: {created_b.text}')
    b_user_id = created_b.json()['item']['id']
    blocked_disable = tenant_a.post(f'/api/users/{b_user_id}/active', json={'is_active': False})
    expect(blocked_disable.status_code == 403, 'tenant admin disabled another tenant user')
    platform_disable = platform.post(f'/api/users/{b_user_id}/active', json={'is_active': False})
    expect(platform_disable.status_code == 200, 'platform admin could not disable cross-tenant user')
    b_logs = tenant_b.get('/api/audit-logs').json()['items']
    expect(any(row['action'] == 'user.disable' for row in b_logs), 'target tenant audit missing platform disable')
    expect('wrong_customer_staff' not in str(platform.get('/api/users').json()), 'blocked platform staff leaked into users')
    print(f'PASS saas acceptance account boundary {label}')


def run_storage_boundary_acceptance(label):
    storage = SaasStorage(root_dir='/var/lib/property-saas')
    system_key = storage.system_asset_path('templates', 'bill.xlsx')
    tenant_key = storage.upload_path(12, 34, 56, 'imports', '../../owners.xlsx')
    expect(system_key.startswith('system/'), 'system key not under system prefix')
    expect(tenant_key.startswith('tenants/12/projects/34/imports/56/original/'), 'tenant upload key not tenant scoped')
    expect(system_key.split('/')[0] != tenant_key.split('/')[0], 'system and tenant storage prefixes overlap')
    expect('..' not in tenant_key and not tenant_key.startswith('/'), 'tenant upload key allows traversal')
    print(f'PASS saas acceptance storage boundary {label}')


def run_import_upload_acceptance(label, database_url=None):
    app = create_app(database_url=database_url)
    client = TestClient(app)
    _login(client, f'导入验收物业-{label}', f'导入验收项目-{label}', 'finance_import', 'finance')
    registered = client.post('/api/imports/files/register', json={
        'import_type': 'charge_targets',
        'original_name': '../../业主房间.xlsx',
        'file_size': 2048,
        'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    expect(registered.status_code == 200, f'import file register failed: {registered.text}')
    item = registered.json()['item']
    expect(item['tenant_id'] > 0 and item['project_id'] > 0, 'import file missing tenant/project scope')
    expect(item['storage_key'].startswith(f"tenants/{item['tenant_id']}/projects/{item['project_id']}/imports/"), 'import file storage key not tenant scoped')
    expect('..' not in item['storage_key'], 'import file storage key allows traversal')
    expect('/system/' not in item['storage_key'] and not item['storage_key'].startswith('system/'), 'customer upload stored in system prefix')
    print(f'PASS saas acceptance import upload {label}')
