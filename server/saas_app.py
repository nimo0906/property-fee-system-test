#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional FastAPI entrypoint for SaaS cloud backoffice deployment."""

from server.saas_backoffice import build_saas_migration_plan, build_saas_postgres_schema


def create_app():
    try:
        from fastapi import FastAPI
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for SaaS deployment; install cloud requirements before running server.saas_app") from exc
    app = FastAPI(title="物业收费管理系统 SaaS 后台")

    @app.get("/health")
    def health():
        return {"ok": True, "service": "property-saas-backoffice"}

    @app.get("/cloud/schema.sql")
    def schema_sql():
        return {"sql": build_saas_postgres_schema()}

    @app.get("/cloud/migration-plan")
    def migration_plan(tenant_name: str = "示例物业", project_name: str = "默认项目"):
        return build_saas_migration_plan(tenant_name, project_name)

    return app


app = create_app() if __name__ != "__main__" else None
