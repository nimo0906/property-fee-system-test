#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Authentication routes and session dependencies for SaaS app."""

from server.passwords import verify_password
from server.saas_login_helpers import repository_login_context, user_must_change_password, verify_repository_login
from server.saas_service import PermissionDenied


def build_auth_dependencies(sessions):
    from fastapi import Cookie, HTTPException

    def session_user(session_id: str = Cookie(default="")):
        user = sessions.get(session_id)
        if not user:
            raise HTTPException(status_code=401, detail="unauthenticated")
        if not user.get("is_active", 1):
            raise HTTPException(status_code=401, detail="inactive user")
        return user

    def current_user(session_id: str = Cookie(default="")):
        user = session_user(session_id)
        if user.get("must_change_password"):
            raise HTTPException(status_code=403, detail="password change required")
        return user

    return current_user, session_user


def register_auth_routes(app, service, repository, sessions, session_user):
    from fastapi import Depends, HTTPException, Response

    from server.saas_api_models import LoginIn, PasswordChangeIn, ProjectSwitchIn

    @app.post("/api/auth/login")
    def login(data: LoginIn, response: Response):
        import secrets
        if repository:
            tenant_row, project_row, user_row = repository_login_context(repository, data)
            if tenant_row.get("status") != "active":
                raise HTTPException(status_code=403, detail="tenant inactive")
            if not verify_repository_login(repository, user_row, data.password):
                raise HTTPException(status_code=401, detail="invalid credentials")
            tenant_id, project_id = tenant_row["id"], project_row["id"]
            service.tenants[tenant_id] = tenant_row
            service.projects[project_id] = project_row
            service.users[user_row["id"]] = {"id": user_row["id"], "tenant_id": tenant_id, "project_id": project_id, "username": data.username, "role_code": data.role_code}
            user = {"id": user_row["id"], "tenant_id": tenant_id, "username": data.username, "role_code": user_row.get("role_code") or data.role_code, "is_active": user_row.get("is_active", 1), "must_change_password": user_must_change_password(repository, user_row["id"])}
        else:
            tenant_id = service.create_tenant(data.tenant_name)
            project_id = service.create_project(tenant_id, data.project_name)
            user = service.create_user(tenant_id, data.username, data.role_code)
        user.update({"tenant_name": data.tenant_name, "project_name": data.project_name, "project_id": project_id, "is_active": user.get("is_active", 1)})
        sid = secrets.token_hex(16)
        sessions[sid] = user
        response.set_cookie("session_id", sid, httponly=True, samesite="lax")
        return {"ok": True, "must_change_password": bool(user.get("must_change_password"))}

    @app.get("/api/auth/me")
    def me(user=Depends(session_user)):
        return {"tenant_name": user["tenant_name"], "project_name": user["project_name"], "project_id": user.get("project_id"), "role_code": user["role_code"], "must_change_password": bool(user.get("must_change_password"))}


    @app.post("/api/auth/switch-project")
    def switch_project(data: ProjectSwitchIn, user=Depends(session_user)):
        try:
            if user.get("must_change_password"):
                raise HTTPException(status_code=403, detail="password change required")
            if repository:
                project = repository.get_project(data.project_id)
                if not project or int(project["tenant_id"]) != int(user["tenant_id"]):
                    raise HTTPException(status_code=403, detail="forbidden")
            else:
                project = service.projects.get(data.project_id)
                if not project or project["tenant_id"] != user["tenant_id"]:
                    raise HTTPException(status_code=403, detail="forbidden")
            user.update({"project_id": project["id"], "project_name": project["name"]})
            return {"ok": True, "project_id": project["id"], "project_name": project["name"]}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/auth/change-password")
    def change_password(data: PasswordChangeIn, user=Depends(session_user)):
        try:
            if repository:
                stored = repository.get_user(user["id"])
                if not stored or not verify_password(data.old_password, stored.get("password_hash")):
                    raise HTTPException(status_code=401, detail="invalid credentials")
                repository.change_own_password(user, data.new_password)
            else:
                stored = service.users.get(user["id"], {})
                if stored.get("password_hash") and not verify_password(data.old_password, stored.get("password_hash")):
                    raise HTTPException(status_code=401, detail="invalid credentials")
                service.reset_user_password(user, user["id"], data.new_password)
            user["must_change_password"] = False
            return {"ok": True, "must_change_password": False}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")
