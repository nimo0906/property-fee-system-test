#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explicit SaaS tenant to license customer binding helpers."""

_BINDINGS_ATTR = 'license_customer_bindings'


def bind_tenant_license_customer(service, repository, user, customer_code):
    if repository:
        # Persistent binding is intentionally kept out of business schema in this slice.
        service = service
    bindings = getattr(service, _BINDINGS_ATTR, None)
    if bindings is None:
        bindings = {}
        setattr(service, _BINDINGS_ATTR, bindings)
    bindings[int(user['tenant_id'])] = str(customer_code or '').strip()
    service._log(user, user['project_id'], 'license.tenant_bind', 'license', None, {'customer_code': bindings[int(user['tenant_id'])]})
    return bindings[int(user['tenant_id'])]


def license_customer_code_for_user(service, repository, user):
    bindings = getattr(service, _BINDINGS_ATTR, {})
    return bindings.get(int(user.get('tenant_id') or 0), '')


def license_customer_code_for_tenant(service, repository, tenant):
    bindings = getattr(service, _BINDINGS_ATTR, {})
    tenant_id = tenant.get('id')
    return bindings.get(int(tenant_id), '') if tenant_id is not None else ''
