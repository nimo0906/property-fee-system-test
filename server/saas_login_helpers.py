#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Login bootstrap helpers for SaaS test/demo authentication."""


def _find_by_name(rows, name, tenant_id=None):
    for row in rows:
        if row.get('name') != name:
            continue
        if tenant_id is None or int(row.get('tenant_id')) == int(tenant_id):
            return row
    return None


def repository_login_context(repository, data):
    tenant_row = _find_by_name(repository.list_tenants(), data.tenant_name)
    if not tenant_row:
        tenant_row = repository.create_tenant(data.tenant_name)
    project_row = _find_by_name(repository.list_projects(), data.project_name, tenant_row['id'])
    if not project_row:
        project_row = repository.create_project(tenant_row['id'], data.project_name)
    user_row = _find_user(repository, tenant_row['id'], data.username)
    if not user_row:
        user_row = repository.create_user(tenant_row['id'], data.username, data.role_code)
    return tenant_row, project_row, user_row


def _find_user(repository, tenant_id, username):
    for row in repository.list_users(tenant_id):
        if row.get('username') == username:
            return row
    return None
