#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI entrypoint for SaaS cloud backoffice deployment."""

from server.saas_backoffice import build_saas_migration_plan, build_saas_postgres_schema
from server.saas_service import PermissionDenied, SaasBackofficeService
from server.saas_repository import create_saas_repository
from server.saas_repository_errors import TenantScopeError
from server.saas_storage import SaasStorage
from server.saas_page_registry import register_saas_pages
from server.saas_billing_api import register_billing_routes
from server.saas_api_models import (
    FeeIn, ImportConfirmIn, ImportFileRegisterIn, ImportPreviewIn,
    LoginIn, PasswordResetIn, RestoreDrillIn, TargetIn, UserActiveIn, UserCreateIn,
)


def create_app(database_url=None):
    try:
        from fastapi import Cookie, FastAPI, HTTPException, Response
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for SaaS deployment; install requirements-saas.txt") from exc

    app = FastAPI(title="物业收费管理系统 SaaS 后台")
    service = SaasBackofficeService.in_memory()
    repository = create_saas_repository(database_url) if database_url else None
    app.state.repository = repository
    sessions = {}
    storage = SaasStorage(root_dir="/var/lib/property-saas")

    def current_user(session_id: str = Cookie(default="")):
        user = sessions.get(session_id)
        if not user:
            raise HTTPException(status_code=401, detail="unauthenticated")
        if not user.get("is_active", 1):
            raise HTTPException(status_code=401, detail="inactive user")
        return user

    app.state.current_user = current_user
    register_saas_pages(app, service, repository, current_user, sessions)
    register_billing_routes(app, service)

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
            service.tenants[tenant_id] = tenant_row
            service.projects[project_id] = project_row
            service.users[user_row["id"]] = {"id": user_row["id"], "tenant_id": tenant_id, "project_id": project_id, "username": data.username, "role_code": data.role_code}
            user = {"id": user_row["id"], "tenant_id": tenant_id, "username": data.username, "role_code": data.role_code, "is_active": user_row.get("is_active", 1)}
        else:
            tenant_id = service.create_tenant(data.tenant_name)
            project_id = service.create_project(tenant_id, data.project_name)
            user = service.create_user(tenant_id, data.username, data.role_code)
        user.update({"tenant_name": data.tenant_name, "project_name": data.project_name, "project_id": project_id, "is_active": user.get("is_active", 1)})
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
                service.users[item["id"]] = {**item, "username": data.username, "role_code": data.role_code}
            else:
                item = service.create_staff_user(user, user["project_id"], data.username, data.role_code)
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))


    @app.get("/api/users")
    def list_users(user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "manage_users")
            items = repository.list_users_for_actor(user) if repository else service.list_staff_users(user, user["project_id"])
            return {"items": items}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/users/{user_id}/active")
    def set_user_active(user_id: int, data: UserActiveIn, user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "manage_users")
            if repository:
                item = repository.set_user_active_for_actor(user, user_id, data.is_active)
            else:
                item = service.set_user_active(user, user["project_id"], user_id, data.is_active)
            sessions_to_drop = [sid for sid, session_user in sessions.items() if session_user.get('id') == user_id]
            if not data.is_active:
                for sid in sessions_to_drop:
                    sessions.pop(sid, None)
            return {"item": item}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/users/{user_id}/reset-password")
    def reset_password(user_id: int, data: PasswordResetIn, user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "manage_users")
            if repository:
                item = repository.reset_user_password_for_actor(user, user_id, data.new_password)
            else:
                item = service.reset_user_password(user, user_id, data.new_password)
            return {"item": item}
        except (PermissionDenied, TenantScopeError):
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/fee-types")
    def create_fee(data: FeeIn, user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "write")
            if repository:
                item = repository.create_fee_type(user["tenant_id"], user["project_id"], data.name, data.unit_price)
                service._log(user, user["project_id"], 'fee_type.create', 'fee_type', item['id'], {'name': data.name, 'unit_price': float(data.unit_price)})
            else:
                item = service.create_fee_type(user, user["project_id"], data.name, data.unit_price)
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/charge-targets")
    def create_target(data: TargetIn, user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "write")
            if repository:
                item = repository.create_charge_target(user["tenant_id"], user["project_id"], data.building, data.unit, data.room_number, data.category, data.area)
                service._log(user, user["project_id"], 'charge_target.create', 'charge_target', item['id'], {'building': data.building, 'room_number': data.room_number})
            else:
                item = service.create_charge_target(user, user["project_id"], data.building, data.unit, data.room_number, data.category, data.area)
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/imports/charge-targets/preview")
    def preview_import(data: ImportPreviewIn, user=__import__('fastapi').Depends(current_user)):
        try:
            return service.preview_charge_target_import(user, user["project_id"], data.rows)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/imports/{import_id}/review")
    def import_review(import_id: int, user=__import__('fastapi').Depends(current_user)):
        try:
            return service.get_import_review(user, user["project_id"], import_id)
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/charge-targets")
    def list_targets(user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "read")
            if repository:
                return {"items": repository.list_charge_targets(user["tenant_id"], user["project_id"])}
            return {"items": service.list_charge_targets(user, user["project_id"])}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/imports/charge-targets/confirm")
    def confirm_import(data: ImportConfirmIn, user=__import__('fastapi').Depends(current_user)):
        try:
            if repository:
                service._require(user, "import")
                review = service.get_import_review(user, user["project_id"], data.import_id)
                if review["confirmed"]:
                    return {"created_count": 0, "skipped_count": review["error_count"]}
                created = 0
                for row in review["valid_rows"]:
                    item = repository.create_charge_target(
                        user["tenant_id"], user["project_id"], row["building"], row.get("unit", ""),
                        row["room_number"], row.get("category", "居民"), row["area"]
                    )
                    service.targets[item["id"]] = item
                    created += 1
                service.imports[data.import_id]["confirmed"] = True
                service._log(user, user["project_id"], 'import.confirm', 'import', data.import_id, {'created_count': created, 'skipped_count': review['error_count']})
                return {"created_count": created, "skipped_count": review["error_count"]}
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

    @app.get("/api/audit-logs")
    def audit_logs(user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "read")
            if repository:
                return {"items": repository.list_audit_logs(user["tenant_id"], user["project_id"])}
            return {"items": service.list_audit_logs(user, user["project_id"])}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/backups/create")
    def create_backup(user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "backup")
            item = repository.create_backup_record(user["tenant_id"], user["project_id"], user["id"]) if repository else service.create_backup_marker(user, user["project_id"])
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/backups")
    def list_backups(user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "backup")
            items = repository.list_backup_records(user["tenant_id"], user["project_id"]) if repository else service.list_backup_records(user, user["project_id"])
            return {"items": items}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/restore-drills")
    def create_restore_drill(data: RestoreDrillIn, user=__import__('fastapi').Depends(current_user)):
        try:
            service._require(user, "backup")
            item = repository.create_restore_drill(user["tenant_id"], user["project_id"], user["id"], data.backup_id, data.scope) if repository else service.record_restore_drill(user, user["project_id"], data.backup_id, data.scope)
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

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
