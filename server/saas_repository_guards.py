#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tenant/project guard helpers for SaaS repository writes."""

from server.saas_repository_errors import TenantScopeError


def validate_bill_scope(repo, tenant_id, project_id, target_id, fee_type_id):
    target = repo.get_charge_target(tenant_id, project_id, target_id)
    fee = repo.get_fee_type(tenant_id, project_id, fee_type_id)
    if not target or not fee:
        raise TenantScopeError("bill target or fee does not belong to tenant project")


def validate_import_storage_key(tenant_id, project_id, storage_key):
    key = str(storage_key or "")
    prefix = f"tenants/{int(tenant_id)}/projects/{int(project_id)}/"
    if not key.startswith(prefix):
        raise TenantScopeError("import file storage key does not belong to tenant project")
    if key.startswith("system/") or "/../" in key or key.startswith("/"):
        raise TenantScopeError("unsafe import file storage key")
