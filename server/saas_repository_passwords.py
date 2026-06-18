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
