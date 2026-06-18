#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI entrypoint for SaaS cloud backoffice deployment."""

from server.saas_backoffice import build_saas_migration_plan, build_saas_postgres_schema
from server.saas_service import PermissionDenied, SaasBackofficeService
from server.saas_repository import create_saas_repository
from server.saas_storage import SaasStorage


def create_app(database_url=None):
    try:
        from fastapi import Cookie, FastAPI, HTTPException, Response
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for SaaS deployment; install requirements-saas.txt") from exc

    app = FastAPI(title="物业收费管理系统 SaaS 后台")
    service = SaasBackofficeService.in_memory()
    repository = create_saas_repository(database_url) if database_url else None
    sessions = {}
    storage = SaasStorage(root_dir="/var/lib/property-saas")

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

    class ImportConfirmIn(BaseModel):
        import_id: int

    class BillGenerateIn(BaseModel):
        target_id: int
        fee_type_id: int
        billing_period: str
        service_start: str
        service_end: str

    class PaymentIn(BaseModel):
        bill_id: int
        amount: float
        method: str = ""
        idempotency_key: str = ""

    class ImportFileRegisterIn(BaseModel):
        import_type: str
        original_name: str
        file_size: int
        content_type: str = ""

    class UserCreateIn(BaseModel):
        username: str
        role_code: str

    class PasswordResetIn(BaseModel):
        new_password: str

    def current_user(session_id: str = Cookie(default="")):
        user = sessions.get(session_id)
        if not user:
            raise HTTPException(status_code=401, detail="unauthenticated")
        return user

    @app.get("/health")
    def health():
        return {"ok": True, "service": "property-saas-backoffice", "storage": "persistent" if repository else "memory"}

    @app.post("/api/auth/login")
    def login(data: LoginIn, response: Response):
        import secrets
        if repository:
            tenant_row = repository.create_tenant(data.tenant_name)
            project_row = repository.create_project(tenant_row["id"], data.project_name)
            user_row = repository.create_user(tenant_row["id"], data.username, data.role_code)
            tenant_id = tenant_row["id"]
            project_id = project_row["id"]
            user = {"id": user_row["id"], "tenant_id": tenant_id, "username": data.username, "role_code": data.role_code}
        else:
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

    @app.post("/api/users")
    def create_user(data: UserCreateIn, user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "manage_users")
            if repository:
                item = repository.create_staff_user(user["tenant_id"], user["project_id"], data.username, data.role_code)
            else:
                item = service.create_staff_user(user, user["project_id"], data.username, data.role_code)
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/users/{user_id}/reset-password")
    def reset_password(user_id: int, data: PasswordResetIn, user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "manage_users")
            item = repository.reset_user_password(user["tenant_id"], user_id, data.new_password) if repository else service.reset_user_password(user, user_id, data.new_password)
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

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

    @app.get("/api/charge-targets")
    def list_targets(user=__import__('fastapi').Depends(current_user)):
        try:
            return {"items": service.list_charge_targets(user, user["project_id"])}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/imports/charge-targets/confirm")
    def confirm_import(data: ImportConfirmIn, user=__import__('fastapi').Depends(current_user)):
        try:
            return service.confirm_charge_target_import(user, user["project_id"], data.import_id)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/imports/files/register")
    def register_import_file(data: ImportFileRegisterIn, user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "import")
            if data.import_type not in {"charge_targets", "attachments", "reports"}:
                raise HTTPException(status_code=400, detail="invalid import type")
            import secrets
            upload_id = secrets.randbelow(900_000_000) + 100_000_000
            storage_key = storage.upload_path(
                tenant_id=user["tenant_id"],
                project_id=user["project_id"],
                upload_id=upload_id,
                category="imports",
                filename=data.original_name,
            )
            if repository:
                item = repository.create_import_file(
                    tenant_id=user["tenant_id"],
                    project_id=user["project_id"],
                    import_type=data.import_type,
                    original_name=data.original_name,
                    storage_key=storage_key,
                    file_size=data.file_size,
                    content_type=data.content_type,
                )
            else:
                item = {
                    "id": upload_id,
                    "tenant_id": user["tenant_id"],
                    "project_id": user["project_id"],
                    "import_type": data.import_type,
                    "status": "uploaded",
                    "original_name": data.original_name,
                    "storage_key": storage_key,
                    "file_size": data.file_size,
                    "content_type": data.content_type,
                }
                service.imports[upload_id] = item
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/bills/generate")
    def generate_bill(data: BillGenerateIn, user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "billing")
            target = service.targets[data.target_id]
            fee = service.fees[data.fee_type_id]
            return {"item": service.generate_bill(user, user["project_id"], target, fee, data.billing_period, data.service_start, data.service_end)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/payments")
    def record_payment(data: PaymentIn, user=__import__('fastapi').Depends(current_user)):
        try:
            return {"item": service.record_payment(user, data.bill_id, data.amount, data.method, data.idempotency_key or None)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/reports/summary")
    def report_summary(period: str, user=__import__('fastapi').Depends(current_user)):
        return service.report(user, user["project_id"], period)

    @app.get("/api/audit-logs")
    def audit_logs(user=__import__('fastapi').Depends(current_user)):
        try:
            return {"items": service.list_audit_logs(user, user["project_id"])}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/backups/create")
    def create_backup(user=__import__('fastapi').Depends(current_user)):
        try:
            return {"item": service.create_backup_marker(user, user["project_id"])}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/admin/bootstrap-state")
    def bootstrap_state():
        if not repository:
            return {"tenants": [], "projects": [], "users": []}
        return {"tenants": repository.list_tenants(), "projects": repository.list_projects(), "users": repository.list_users()}

    @app.get("/cloud/schema.sql")
    def schema_sql():
        return {"sql": build_saas_postgres_schema()}

    @app.get("/cloud/migration-plan")
    def migration_plan(tenant_name: str = "示例物业", project_name: str = "默认项目"):
        return build_saas_migration_plan(tenant_name, project_name)

    return app


app = create_app()
