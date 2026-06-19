#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explicit SaaS tenant to license customer binding helpers."""

_BINDINGS_ATTR = 'license_customer_bindings'


def bind_tenant_license_customer(service, repository, user, customer_code, store=None):
    if repository:
        # Persistent binding is intentionally kept out of business schema in this slice.
        service = service
    bindings = _bindings(service, store)
    bindings[int(user['tenant_id'])] = str(customer_code or '').strip()
    if store:
        store.save(bindings)
    service._log(user, user['project_id'], 'license.tenant_bind', 'license', None, {'customer_code': bindings[int(user['tenant_id'])]})
    return bindings[int(user['tenant_id'])]


def license_customer_code_for_user(service, repository, user, store=None):
    bindings = _bindings(service, store)
    return bindings.get(int(user.get('tenant_id') or 0), '')


def license_customer_code_for_tenant(service, repository, tenant, store=None):
    bindings = _bindings(service, store)
    tenant_id = tenant.get('id')
    return bindings.get(int(tenant_id), '') if tenant_id is not None else ''


def _bindings(service, store=None):
    bindings = getattr(service, _BINDINGS_ATTR, None)
    if bindings is None:
        bindings = store.load() if store else {}
        setattr(service, _BINDINGS_ATTR, bindings)
    return bindings
