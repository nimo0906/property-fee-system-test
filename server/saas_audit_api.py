#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit log API routes for SaaS backoffice."""

from server.saas_audit_tools import filter_audit_items, sanitize_audit_item
from server.saas_service import PermissionDenied


def register_audit_api(app, service, repository):
    from fastapi import Depends, HTTPException

    current_user = app.state.current_user

    def _items_for(user):
        if repository:
            return repository.list_audit_logs(user["tenant_id"], user["project_id"])
        return service.list_audit_logs(user, user["project_id"])

    @app.get("/api/audit-logs")
    def audit_logs(action: str = "", entity_type: str = "", keyword: str = "", risk: str = "", user=Depends(current_user)):
        try:
            service._require(user, "read")
            return {"items": filter_audit_items(_items_for(user), action, entity_type, keyword, risk)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/audit-logs/{log_id}")
    def audit_log_detail(log_id: int, user=Depends(current_user)):
        try:
            service._require(user, "read")
            item = next((row for row in _items_for(user) if int(row.get("id")) == int(log_id)), None)
            if not item:
                raise HTTPException(status_code=404, detail="audit log not found")
            return {"item": sanitize_audit_item(item)}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")
