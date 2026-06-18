#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI entrypoint for SaaS cloud backoffice deployment."""

from server.saas_backoffice import build_saas_migration_plan, build_saas_postgres_schema
from server.saas_service import PermissionDenied, SaasBackofficeService


def create_app():
    try:
        from fastapi import Cookie, FastAPI, HTTPException, Response
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for SaaS deployment; install requirements-saas.txt") from exc

    app = FastAPI(title="物业收费管理系统 SaaS 后台")
    service = SaasBackofficeService.in_memory()
    sessions = {}

    class LoginIn(BaseModel):
        tenant_name: str
        project_name: str
        username: str
        role_code: str

    class FeeIn(BaseModel):
        name: str
        unit_price: float

    class TargetIn(BaseModel):
        building: str
        unit: str = ""
        room_number: str
        category: str = "居民"
        area: float

    class ImportPreviewIn(BaseModel):
        rows: list

    def current_user(session_id: str = Cookie(default="")):
        user = sessions.get(session_id)
        if not user:
            raise HTTPException(status_code=401, detail="unauthenticated")
        return user

    @app.get("/health")
    def health():
        return {"ok": True, "service": "property-saas-backoffice"}

    @app.post("/api/auth/login")
    def login(data: LoginIn, response: Response):
        import secrets
        tenant_id = service.create_tenant(data.tenant_name)
        project_id = service.create_project(tenant_id, data.project_name)
        user = service.create_user(tenant_id, data.username, data.role_code)
        user.update({"tenant_name": data.tenant_name, "project_name": data.project_name, "project_id": project_id})
        sid = secrets.token_hex(16)
        sessions[sid] = user
        response.set_cookie("session_id", sid, httponly=True, samesite="lax")
        return {"ok": True}

    @app.get("/api/auth/me")
    def me(user=__import__('fastapi').Depends(current_user)):
        return {"tenant_name": user["tenant_name"], "project_name": user["project_name"], "role_code": user["role_code"]}

    @app.post("/api/fee-types")
    def create_fee(data: FeeIn, user=__import__('fastapi').Depends(current_user)):
        try:
            return {"item": service.create_fee_type(user, user["project_id"], data.name, data.unit_price)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/charge-targets")
    def create_target(data: TargetIn, user=__import__('fastapi').Depends(current_user)):
        try:
            return {"item": service.create_charge_target(user, user["project_id"], data.building, data.unit, data.room_number, data.category, data.area)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/imports/charge-targets/preview")
    def preview_import(data: ImportPreviewIn, user=__import__('fastapi').Depends(current_user)):
        try:
            return service.preview_charge_target_import(user, user["project_id"], data.rows)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/cloud/schema.sql")
    def schema_sql():
        return {"sql": build_saas_postgres_schema()}

    @app.get("/cloud/migration-plan")
    def migration_plan(tenant_name: str = "示例物业", project_name: str = "默认项目"):
        return build_saas_migration_plan(tenant_name, project_name)

    return app


app = create_app()
