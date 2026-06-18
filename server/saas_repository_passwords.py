#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Password reset helper for SaaS repository."""

from sqlalchemy import text

from server.passwords import hash_password
from server.saas_repository_errors import TenantScopeError


def reset_user_password_record(repo, tenant_id, user_id, new_password):
    target = repo.get_user(user_id)
    if not target or int(target['tenant_id']) != int(tenant_id):
        raise TenantScopeError('user does not belong to tenant')
    with repo.engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET password_hash=:password_hash WHERE id=:id AND tenant_id=:tenant_id"),
            {'id': user_id, 'tenant_id': tenant_id, 'password_hash': hash_password(new_password)},
        )
    return target


def list_user_records(repo, tenant_id=None):
    sql = "SELECT id,tenant_id,username,role_code,is_active FROM users"
    params = {}
    if tenant_id is not None:
        sql += " WHERE tenant_id=:tenant_id"
        params['tenant_id'] = tenant_id
    sql += " ORDER BY id"
    with repo.engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]


def set_user_active_record(repo, tenant_id, user_id, is_active):
    target = repo.get_user(user_id)
    if not target or int(target['tenant_id']) != int(tenant_id):
        raise TenantScopeError('user does not belong to tenant')
    active_value = 1 if is_active else 0
    with repo.engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET is_active=:is_active WHERE id=:id AND tenant_id=:tenant_id"),
            {'id': user_id, 'tenant_id': tenant_id, 'is_active': active_value},
        )
    target['is_active'] = active_value
    return target


def _repo_list_users(self, tenant_id=None):
    return list_user_records(self, tenant_id)


def _repo_set_user_active(self, tenant_id, user_id, is_active, actor_user_id=None, project_id=None):
    target = set_user_active_record(self, tenant_id, user_id, is_active)
    if actor_user_id and project_id:
        action = 'user.enable' if is_active else 'user.disable'
        self.create_audit_log(tenant_id, project_id, actor_user_id, action, 'user', user_id, {
            'target_user_id': user_id,
            'target_username': target.get('username'),
            'target_role_code': target.get('role_code'),
            'new_is_active': bool(is_active),
        })
    return {'user_id': user_id, 'is_active': target['is_active']}


def _repo_reset_user_password(self, tenant_id, user_id, new_password, actor_user_id=None, project_id=None):
    target = reset_user_password_record(self, tenant_id, user_id, new_password)
    if actor_user_id and project_id:
        self.create_audit_log(tenant_id, project_id, actor_user_id, 'user.password_reset', 'user', user_id, {
            'target_user_id': user_id,
            'target_username': target.get('username'),
            'target_role_code': target.get('role_code'),
            'password_changed': True,
        })
    return {'user_id': user_id}


def attach_user_lifecycle_methods(cls):
    cls.list_users = _repo_list_users
    cls.set_user_active = _repo_set_user_active
    cls.reset_user_password = _repo_reset_user_password
