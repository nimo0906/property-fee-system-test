#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime tenant isolation self-check for SaaS backoffice."""

from sqlalchemy import text


def _check(name, leaked):
    return {
        'name': name,
        'status': 'fail' if leaked else 'pass',
        'message': 'blocked cross-tenant read' if not leaked else 'cross-tenant data leaked',
    }


def _cleanup_repository_canary(repo, tenant_id):
    if not tenant_id:
        return
    tables = [
        'audit_logs', 'payments', 'bills', 'fee_types', 'charge_targets',
        'imports', 'backup_records', 'restore_drills', 'users', 'projects',
    ]
    with repo.engine.begin() as conn:
        for table in tables:
            conn.execute(text(f'DELETE FROM {table} WHERE tenant_id=:tenant_id'), {'tenant_id': tenant_id})
        conn.execute(text('DELETE FROM tenants WHERE id=:tenant_id'), {'tenant_id': tenant_id})


def _run_repository_check(user, repo):
    canary_tenant = None
    try:
        canary_tenant = repo.create_tenant(f"隔离自检金丝雀-{user['tenant_id']}-{user['project_id']}")
        canary_project = repo.create_project(canary_tenant['id'], '隔离自检项目')
        canary_user = repo.create_user(canary_tenant['id'], 'isolation_canary', 'finance')
        target = repo.create_charge_target(canary_tenant['id'], canary_project['id'], '金丝雀楼', '1单元', '101', '测试', 1)
        fee = repo.create_fee_type(canary_tenant['id'], canary_project['id'], '金丝雀费用', 1)
        bill = repo.create_bill(canary_tenant['id'], canary_project['id'], target['id'], fee['id'], '2099-01', '2099-01-01', '2099-01-31', 1, actor_user_id=canary_user['id'])
        repo.approve_bill(canary_tenant['id'], canary_project['id'], bill['id'], actor_user_id=canary_user['id'])
        repo.create_payment(canary_tenant['id'], canary_project['id'], bill['id'], 1, 'cash', 'isolation-canary', actor_user_id=canary_user['id'])
        repo.create_import_file(canary_tenant['id'], canary_project['id'], 'charge_targets', 'canary.xlsx', f"tenants/{canary_tenant['id']}/projects/{canary_project['id']}/imports/1/original/canary.xlsx", 1, 'application/octet-stream')
        checks = [
            _check('收费对象', any(row.get('tenant_id') == canary_tenant['id'] for row in repo.list_charge_targets(user['tenant_id'], user['project_id']))),
            _check('账单', any(row.get('tenant_id') == canary_tenant['id'] for row in repo.list_bills(user['tenant_id'], user['project_id']))),
            _check('收款', any(row.get('tenant_id') == canary_tenant['id'] for row in repo.search_payments(user['tenant_id'], user['project_id'], '', None, 1, 50)['items'])),
            _check('导入文件', any(row.get('tenant_id') == canary_tenant['id'] for row in repo.list_import_files(user['tenant_id'], user['project_id']))),
            _check('审计日志', any(row.get('tenant_id') == canary_tenant['id'] for row in repo.list_audit_logs(user['tenant_id'], user['project_id']))),
        ]
        return _result(checks)
    finally:
        _cleanup_repository_canary(repo, canary_tenant['id'] if canary_tenant else None)


def _run_memory_check(user, service):
    tenant_id = service.create_tenant('隔离自检金丝雀')
    project_id = service.create_project(tenant_id, '隔离自检项目')
    canary_user = service.create_user(tenant_id, 'isolation_canary', 'finance')
    target = service.create_charge_target(canary_user, project_id, '金丝雀楼', '1单元', '101', '测试', 1)
    fee = service.create_fee_type(canary_user, project_id, '金丝雀费用', 1)
    bill = service.generate_bill(canary_user, project_id, target, fee, '2099-01', '2099-01-01', '2099-01-31')
    service.approve_bill(canary_user, project_id, bill['id'])
    service.record_payment(canary_user, bill['id'], 1, 'cash', 'isolation-canary')
    import_id = 999_900 + int(tenant_id)
    service.imports[import_id] = {'tenant_id': tenant_id, 'project_id': project_id, 'original_name': 'canary.xlsx'}
    try:
        checks = [
            _check('收费对象', any(row.get('tenant_id') == tenant_id for row in service.list_charge_targets(user, user['project_id']))),
            _check('账单', any(row.get('tenant_id') == tenant_id for row in service.list_bills(user, user['project_id']))),
            _check('收款', any(row.get('tenant_id') == tenant_id for row in service.search_payments(user, user['project_id'])['items'])),
            _check('导入文件', any(row.get('tenant_id') == tenant_id for row in service.imports.values() if row.get('project_id') == user['project_id'])),
            _check('审计日志', any(row.get('tenant_id') == tenant_id for row in service.list_audit_logs(user, user['project_id']))),
        ]
        return _result(checks)
    finally:
        service.audit_logs = [row for row in service.audit_logs if row.get('tenant_id') != tenant_id]
        for bucket in [service.payments, service.bills, service.fees, service.targets, service.imports, service.users, service.projects]:
            for key, row in list(bucket.items()):
                if row.get('tenant_id') == tenant_id:
                    bucket.pop(key, None)
        service.tenants.pop(tenant_id, None)


def _result(checks):
    status = 'pass' if all(item['status'] == 'pass' for item in checks) else 'fail'
    return {'status': status, 'checked_scope': 'current_tenant_project', 'checks': checks}


def run_isolation_self_check(user, service, repository=None):
    if repository:
        return _run_repository_check(user, repository)
    return _run_memory_check(user, service)


def register_isolation_self_check_api(app, service, repository, current_user):
    from fastapi import Depends

    @app.post('/api/isolation/self-check')
    def isolation_self_check(user=Depends(current_user)):
        return run_isolation_self_check(user, service, repository)
