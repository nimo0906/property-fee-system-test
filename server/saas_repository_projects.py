#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant project helpers for SaaS repository."""

from sqlalchemy import text

from server.passwords import hash_password
from server.saas_service import PermissionDenied


def _repo_list_projects(self, tenant_id=None):
    sql = "SELECT id,tenant_id,name,code,is_active FROM projects"
    params = {}
    if tenant_id is not None:
        sql += " WHERE tenant_id=:tenant_id"
        params["tenant_id"] = tenant_id
    sql += " ORDER BY id"
    with self.engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]


def _repo_create_project_for_actor(self, actor, name, code=None):
    if actor.get("role_code") != "system_admin":
        raise PermissionDenied("tenant admin only")
    item = self.create_project(actor["tenant_id"], name, code)
    self.create_audit_log(
        actor["tenant_id"], actor["project_id"], actor.get("id"),
        "project.create", "project", item["id"], {"name": name, "code": code},
    )
    return item


def attach_project_methods(cls):
    cls.list_projects = _repo_list_projects
    cls.create_project_for_actor = _repo_create_project_for_actor
    cls.onboard_tenant_for_platform = _repo_onboard_tenant_for_platform
    cls.set_tenant_status_for_platform = _repo_set_tenant_status_for_platform
    return cls


def _repo_onboard_tenant_for_platform(self, actor, tenant_name, project_name, admin_username, admin_password, project_code=None):
    if actor.get("role_code") != "platform_admin":
        raise PermissionDenied("platform admin only")
    tenant = self.create_tenant(tenant_name)
    project = self.create_project(tenant["id"], project_name, project_code)
    admin = self.create_user(tenant["id"], admin_username, "system_admin", hash_password(admin_password))
    self.create_audit_log(tenant["id"], project["id"], actor.get("id"), "tenant.create", "tenant", tenant["id"], {"tenant_name": tenant_name, "actor_username": actor.get("username"), "scope": "platform"})
    self.create_audit_log(tenant["id"], project["id"], actor.get("id"), "project.create", "project", project["id"], {"name": project_name, "code": project_code, "scope": "platform"})
    self.create_audit_log(tenant["id"], project["id"], actor.get("id"), "user.create", "user", admin["id"], {"username": admin_username, "role_code": "system_admin", "scope": "platform"})
    self.create_audit_log(tenant["id"], project["id"], actor.get("id"), "user.password_reset", "user", admin["id"], {"target_username": admin_username, "target_role_code": "system_admin", "password_changed": True, "force_change": True, "scope": "platform"})
    return {"tenant": tenant, "project": project, "admin": admin}


def _repo_set_tenant_status_for_platform(self, actor, tenant_id, status):
    if actor.get("role_code") != "platform_admin":
        raise PermissionDenied("platform admin only")
    if status not in {"active", "suspended"}:
        raise ValueError("invalid tenant status")
    tenant = self.get_tenant(tenant_id)
    if not tenant:
        raise PermissionDenied("tenant not found")
    with self.engine.begin() as conn:
        conn.execute(text("UPDATE tenants SET status=:status WHERE id=:tenant_id"), {"status": status, "tenant_id": tenant_id})
    project = self._row("SELECT id FROM projects WHERE tenant_id=:tenant_id ORDER BY id LIMIT 1", {"tenant_id": tenant_id})
    if project:
        action = "tenant.activate" if status == "active" else "tenant.suspend"
        self.create_audit_log(tenant_id, project["id"], actor.get("id"), action, "tenant", tenant_id, {"tenant_name": tenant.get("name"), "status": status, "scope": "platform", "actor_username": actor.get("username")})
    tenant["status"] = status
    return tenant
