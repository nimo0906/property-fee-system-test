#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI owner routes for SaaS backoffice."""

from server.saas_api_models import OwnerIn
from server.saas_service import PermissionDenied


def register_owner_routes(app, service):
    from fastapi import Depends, HTTPException

    current_user = app.state.current_user
    repository = getattr(app.state, "repository", None)

    @app.post("/api/owners")
    def create_owner(data: OwnerIn, user=Depends(current_user)):
        try:
            service._require(user, "write")
            if repository:
                item = repository.create_owner(user["tenant_id"], user["project_id"], data.name, data.phone, data.owner_type)
                repository.create_audit_log(user["tenant_id"], user["project_id"], user["id"], "owner.create", "owner", item["id"], {"name": data.name, "owner_type": data.owner_type})
            else:
                item = service.create_owner(user, user["project_id"], data.name, data.phone, data.owner_type)
            return {"item": item}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/api/owners")
    def list_owners(user=Depends(current_user)):
        try:
            service._require(user, "read")
            items = repository.list_owners(user["tenant_id"], user["project_id"]) if repository else service.list_owners(user, user["project_id"])
            return {"items": items}
        except PermissionDenied:
            raise HTTPException(status_code=403, detail="forbidden")
