#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backup and restore drill API routes for SaaS backoffice."""

from server.saas_api_models import RestoreDrillIn
from server.saas_backup_view import backup_items, restore_drill_items
from server.saas_service import PermissionDenied


def register_backup_api(app, service, repository):
    from fastapi import Depends, HTTPException

    current_user = app.state.current_user

    def _records(user):
        if repository:
            return repository.list_backup_records(user["tenant_id"], user["project_id"])
        return service.list_backup_records(user, user["project_id"])

    def _drills(user):
        if repository:
            return repository.list_restore_drills(user["tenant_id"], user["project_id"])
        return [r for r in service.restore_drills.values() if r["tenant_id"] == user["tenant_id"] and r["project_id"] == user["project_id"]]

    def _context(user):
        if repository:
            return repository.list_users(user["tenant_id"]), repository.list_audit_logs(user["tenant_id"], user["project_id"])
        return [u for u in service.users.values() if u["tenant_id"] == user["tenant_id"]], service.list_audit_logs(user, user["project_id"])

    @app.post("/api/backups/create")
    def create_backup(user=Depends(current_user)):
        try:
            service._require(user, "backup")
            item = repository.create_backup_record(user["tenant_id"], user["project_id"], user["id"]) if repository else service.create_backup_marker(user, user["project_id"])
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/backups")
    def list_backups(user=Depends(current_user)):
        try:
            service._require(user, "backup")
            users, audits = _context(user)
            return {"items": backup_items(_records(user), users, audits)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/api/restore-drills")
    def create_restore_drill(data: RestoreDrillIn, user=Depends(current_user)):
        try:
            service._require(user, "backup")
            if data.backup_id not in {r.get("backup_id") for r in _records(user)}:
                raise PermissionDenied("backup does not belong to tenant")
            item = repository.create_restore_drill(user["tenant_id"], user["project_id"], user["id"], data.backup_id, data.scope) if repository else service.record_restore_drill(user, user["project_id"], data.backup_id, data.scope)
            return {"item": item}
        except (PermissionDenied, ValueError):
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/restore-drills")
    def list_restore_drills(user=Depends(current_user)):
        try:
            service._require(user, "backup")
            users, audits = _context(user)
            return {"items": restore_drill_items(_drills(user), users, audits)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")
