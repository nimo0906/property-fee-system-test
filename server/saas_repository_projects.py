#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant project helpers for SaaS repository."""

from sqlalchemy import text

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
    return cls
