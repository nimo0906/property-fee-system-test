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



def change_user_password_record(repo, tenant_id, user_id, new_password):
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
    sql = """SELECT u.id,u.tenant_id,t.name AS tenant_name,u.username,u.role_code,u.is_active
        FROM users u JOIN tenants t ON t.id=u.tenant_id"""
    params = {}
    if tenant_id is not None:
        sql += " WHERE u.tenant_id=:tenant_id"
        params['tenant_id'] = tenant_id
    sql += " ORDER BY u.id"
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



def _target_project_id(repo, target):
    project = repo._row("SELECT id FROM projects WHERE tenant_id=:tenant_id ORDER BY id LIMIT 1", {'tenant_id': target['tenant_id']})
    return project['id'] if project else None


def _platform_detail(actor, target, extra=None):
    detail = {
        'target_user_id': target['id'],
        'target_username': target.get('username'),
        'target_role_code': target.get('role_code'),
        'scope': 'platform',
        'actor_username': actor.get('username'),
        'actor_tenant_id': actor.get('tenant_id'),
    }
    if extra:
        detail.update(extra)
    return detail

def _repo_list_users(self, tenant_id=None):
    return list_user_records(self, tenant_id)


def _repo_set_user_active(self, tenant_id, user_id, is_active, actor_user_id=None, project_id=None):
    target = set_user_active_record(self, tenant_id, user_id, is_active)
    _audit_user_active(self, tenant_id, user_id, is_active, target, actor_user_id, project_id)
    return {'user_id': user_id, 'is_active': target['is_active']}


def _audit_user_active(repo, tenant_id, user_id, is_active, target, actor_user_id, project_id, detail=None):
    if not actor_user_id or not project_id:
        return
    action = 'user.enable' if is_active else 'user.disable'
    payload = detail or {
        'target_user_id': user_id,
        'target_username': target.get('username'),
        'target_role_code': target.get('role_code'),
        'new_is_active': bool(is_active),
    }
    repo.create_audit_log(tenant_id, project_id, actor_user_id, action, 'user', user_id, payload)


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
    cls.list_users_for_actor = _repo_list_users_for_actor
    cls.set_user_active = _repo_set_user_active
    cls.set_user_active_for_actor = _repo_set_user_active_for_actor
    cls.reset_user_password = _repo_reset_user_password
    cls.reset_user_password_for_actor = _repo_reset_user_password_for_actor
    cls.change_own_password = _repo_change_own_password


def _repo_list_users_for_actor(self, actor):
    if actor.get('role_code') == 'platform_admin':
        return list_user_records(self)
    return list_user_records(self, actor['tenant_id'])


def _repo_reset_user_password_for_actor(self, actor, user_id, new_password):
    target = self.get_user(user_id)
    if not target:
        raise TenantScopeError('user does not belong to tenant')
    if actor.get('role_code') != 'platform_admin' and int(target['tenant_id']) != int(actor['tenant_id']):
        raise TenantScopeError('user does not belong to tenant')
    reset_user_password_record(self, target['tenant_id'], user_id, new_password)
    project_id = _target_project_id(self, target)
    if project_id:
        detail = {
            'target_user_id': user_id,
            'target_username': target.get('username'),
            'target_role_code': target.get('role_code'),
            'password_changed': True,
        }
        if actor.get('role_code') == 'platform_admin' and int(target['tenant_id']) != int(actor['tenant_id']):
            detail = _platform_detail(actor, target, {'password_changed': True})
        self.create_audit_log(target['tenant_id'], project_id, actor.get('id'), 'user.password_reset', 'user', user_id, detail)
    return {'user_id': user_id}


def _repo_set_user_active_for_actor(self, actor, user_id, is_active):
    target = self.get_user(user_id)
    if not target:
        raise TenantScopeError('user does not belong to tenant')
    cross_tenant = int(target['tenant_id']) != int(actor['tenant_id'])
    if cross_tenant and actor.get('role_code') != 'platform_admin':
        raise TenantScopeError('user does not belong to tenant')
    set_user_active_record(self, target['tenant_id'], user_id, is_active)
    project_id = _target_project_id(self, target)
    if project_id:
        detail = {
            'target_user_id': user_id,
            'target_username': target.get('username'),
            'target_role_code': target.get('role_code'),
            'new_is_active': bool(is_active),
        }
        if cross_tenant:
            detail = _platform_detail(actor, target, {'new_is_active': bool(is_active)})
        _audit_user_active(self, target['tenant_id'], user_id, is_active, target, actor.get('id'), project_id, detail)
    return {'user_id': user_id, 'is_active': 1 if is_active else 0}


def _repo_change_own_password(self, user, new_password):
    target = change_user_password_record(self, user['tenant_id'], user['id'], new_password)
    project_id = user.get('project_id') or _target_project_id(self, target)
    if project_id:
        self.create_audit_log(user['tenant_id'], project_id, user.get('id'), 'user.password_change', 'user', user['id'], {'password_changed': True})
    return {'user_id': user['id']}
