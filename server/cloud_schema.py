#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PostgreSQL cloud schema draft for the commercial-complex v2 backend."""


def build_postgres_schema():
    """Return the first cloud PostgreSQL schema slice.

    This is intentionally generated as SQL text so the existing SQLite desktop
    runtime can keep working while v2 cloud migration tooling is built around a
    stable, reviewable schema contract.
    """
    return """
CREATE TABLE IF NOT EXISTS cloud_projects (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cloud_roles (
    id BIGSERIAL PRIMARY KEY,
    role_code TEXT NOT NULL UNIQUE,
    role_name TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS merchant_contracts (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES cloud_projects(id),
    room_id BIGINT NOT NULL,
    owner_id BIGINT,
    contract_no TEXT NOT NULL,
    merchant_name TEXT NOT NULL,
    shop_name TEXT,
    rent_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    rent_cycle TEXT NOT NULL DEFAULT 'monthly',
    property_rate NUMERIC(12,4) NOT NULL DEFAULT 0,
    property_cycle TEXT NOT NULL DEFAULT 'monthly',
    deposit_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contract_bill_runs (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES cloud_projects(id),
    contract_id BIGINT NOT NULL REFERENCES merchant_contracts(id),
    billing_period TEXT NOT NULL,
    generated_count INTEGER NOT NULL DEFAULT 0,
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    operator TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(contract_id, billing_period)
);

CREATE TABLE IF NOT EXISTS cloud_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT REFERENCES cloud_projects(id),
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id BIGINT,
    username TEXT,
    role_code TEXT NOT NULL,
    ip TEXT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
""".strip()
