#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLAlchemy-backed repository for SaaS tenant/project/RBAC seed data."""

from sqlalchemy import create_engine, text


class SaasRepository:
    def __init__(self, url):
        self.engine = create_engine(url, future=True)
        self._init_schema()

    def close(self):
        self.engine.dispose()

    def _init_schema(self):
        stmts = [
            "CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active')",
            "CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,name TEXT NOT NULL,code TEXT,is_active INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,name))",
            "CREATE TABLE IF NOT EXISTS roles(code TEXT PRIMARY KEY,name TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS permissions(code TEXT PRIMARY KEY,name TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS role_permissions(role_code TEXT NOT NULL,permission_code TEXT NOT NULL,PRIMARY KEY(role_code,permission_code))",
            "CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER NOT NULL,username TEXT NOT NULL,role_code TEXT NOT NULL,password_hash TEXT,is_active INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,username))",
        ]
        with self.engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))

    def _row(self, sql, params):
        with self.engine.begin() as conn:
            row = conn.execute(text(sql), params).mappings().first()
            return dict(row) if row else None

    def create_tenant(self, name):
        with self.engine.begin() as conn:
            result = conn.execute(text("INSERT INTO tenants(name) VALUES(:name)"), {"name": name})
            return {"id": result.lastrowid, "name": name, "status": "active"}

    def get_tenant(self, tenant_id):
        return self._row("SELECT id,name,status FROM tenants WHERE id=:id", {"id": tenant_id})

    def create_project(self, tenant_id, name, code=None):
        with self.engine.begin() as conn:
            result = conn.execute(text("INSERT INTO projects(tenant_id,name,code) VALUES(:tenant_id,:name,:code)"), {"tenant_id": tenant_id, "name": name, "code": code})
            return {"id": result.lastrowid, "tenant_id": tenant_id, "name": name, "code": code}

    def get_project(self, project_id):
        return self._row("SELECT id,tenant_id,name,code,is_active FROM projects WHERE id=:id", {"id": project_id})

    def upsert_role(self, code, name):
        with self.engine.begin() as conn:
            conn.execute(text("INSERT OR REPLACE INTO roles(code,name) VALUES(:code,:name)"), {"code": code, "name": name})
        return {"code": code, "name": name}

    def upsert_permission(self, code, name):
        with self.engine.begin() as conn:
            conn.execute(text("INSERT OR REPLACE INTO permissions(code,name) VALUES(:code,:name)"), {"code": code, "name": name})
        return {"code": code, "name": name}

    def grant_permission(self, role_code, permission_code):
        with self.engine.begin() as conn:
            conn.execute(text("INSERT OR IGNORE INTO role_permissions(role_code,permission_code) VALUES(:role_code,:permission_code)"), {"role_code": role_code, "permission_code": permission_code})
        return {"role_code": role_code, "permission_code": permission_code}

    def list_permissions_for_role(self, role_code):
        with self.engine.begin() as conn:
            rows = conn.execute(text("SELECT permission_code FROM role_permissions WHERE role_code=:role_code ORDER BY permission_code"), {"role_code": role_code}).fetchall()
            return [row[0] for row in rows]

    def create_user(self, tenant_id, username, role_code, password_hash=None):
        with self.engine.begin() as conn:
            result = conn.execute(text("INSERT INTO users(tenant_id,username,role_code,password_hash) VALUES(:tenant_id,:username,:role_code,:password_hash)"), {"tenant_id": tenant_id, "username": username, "role_code": role_code, "password_hash": password_hash})
            return {"id": result.lastrowid, "tenant_id": tenant_id, "username": username, "role_code": role_code}

    def get_user(self, user_id):
        return self._row("SELECT id,tenant_id,username,role_code,password_hash,is_active FROM users WHERE id=:id", {"id": user_id})


def create_saas_repository(url):
    return SaasRepository(url)
