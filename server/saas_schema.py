#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS PostgreSQL schema contract for cloud backoffice."""


def build_saas_postgres_schema():
    return """
CREATE TABLE IF NOT EXISTS tenants (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    code TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, name)
);

CREATE TABLE IF NOT EXISTS roles (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS permissions (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_code TEXT NOT NULL REFERENCES roles(code),
    permission_code TEXT NOT NULL REFERENCES permissions(code),
    PRIMARY KEY(role_code, permission_code)
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    username TEXT NOT NULL,
    role_code TEXT NOT NULL REFERENCES roles(code),
    password_hash TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, username)
);

CREATE TABLE IF NOT EXISTS owners (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    project_id BIGINT NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    phone TEXT,
    id_card_masked TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS charge_targets (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    project_id BIGINT NOT NULL REFERENCES projects(id),
    owner_id BIGINT REFERENCES owners(id),
    building TEXT NOT NULL,
    unit TEXT,
    room_number TEXT NOT NULL,
    category TEXT NOT NULL,
    area NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, project_id, building, unit, room_number)
);

CREATE TABLE IF NOT EXISTS fee_types (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    project_id BIGINT NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    unit_price NUMERIC(12,4) NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(tenant_id, project_id, name)
);

CREATE TABLE IF NOT EXISTS bills (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    project_id BIGINT NOT NULL REFERENCES projects(id),
    charge_target_id BIGINT NOT NULL REFERENCES charge_targets(id),
    fee_type_id BIGINT NOT NULL REFERENCES fee_types(id),
    bill_number TEXT NOT NULL,
    billing_period TEXT NOT NULL,
    service_start DATE,
    service_end DATE,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'unpaid',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, project_id, bill_number)
);

CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    project_id BIGINT NOT NULL REFERENCES projects(id),
    bill_id BIGINT NOT NULL REFERENCES bills(id),
    amount_paid NUMERIC(12,2) NOT NULL,
    method TEXT,
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS imports (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    project_id BIGINT NOT NULL REFERENCES projects(id),
    import_type TEXT NOT NULL,
    status TEXT NOT NULL,
    original_name TEXT,
    storage_key TEXT,
    file_size BIGINT,
    content_type TEXT,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    project_id BIGINT REFERENCES projects(id),
    user_id BIGINT REFERENCES users(id),
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id BIGINT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
""".strip()
