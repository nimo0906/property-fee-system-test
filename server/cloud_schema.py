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

INSERT INTO cloud_roles(role_code, role_name, notes) VALUES
    ('system_admin', '系统管理员', '系统维护、更新、备份恢复、账号与全部业务权限'),
    ('finance', '财务', '合同、出账、收费、发票、催缴、对账、结账'),
    ('cashier', '收费员', '日常收费、收据、缴费记录'),
    ('frontdesk', '客服业务编辑', '维护业主、房间、合同、抄表、导入资料并跟进催缴；不收款不结账'),
    ('executive', '管理层只读', '查看驾驶舱、报表和风险预警')
ON CONFLICT (role_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS cloud_users (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT REFERENCES cloud_projects(id),
    username TEXT NOT NULL UNIQUE,
    display_name TEXT,
    role_code TEXT NOT NULL REFERENCES cloud_roles(role_code),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
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
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contract_attachments (
    id BIGSERIAL PRIMARY KEY,
    contract_id BIGINT NOT NULL REFERENCES merchant_contracts(id),
    attachment_type TEXT,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    file_ext TEXT NOT NULL,
    mime_type TEXT,
    file_size BIGINT NOT NULL DEFAULT 0,
    uploaded_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cloud_bills (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES cloud_projects(id),
    room_id BIGINT NOT NULL,
    owner_id BIGINT,
    fee_type_id BIGINT NOT NULL,
    billing_period TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'unpaid',
    due_date DATE,
    bill_number TEXT NOT NULL,
    source TEXT,
    source_ref TEXT,
    service_start DATE,
    service_end DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, source, source_ref, fee_type_id, service_start, service_end)
);

CREATE TABLE IF NOT EXISTS cloud_payments (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES cloud_projects(id),
    bill_id BIGINT NOT NULL REFERENCES cloud_bills(id),
    amount_paid NUMERIC(12,2) NOT NULL,
    payment_date DATE NOT NULL,
    method TEXT,
    operator TEXT,
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
