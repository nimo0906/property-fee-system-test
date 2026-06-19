#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialect-specific bootstrap SQL for SaaS repository."""

TABLES = [
    ('tenants', 'id {pk},name TEXT NOT NULL,status TEXT NOT NULL DEFAULT \'active\''),
    ('projects', 'id {pk},tenant_id INTEGER NOT NULL,name TEXT NOT NULL,code TEXT,is_active INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,name)'),
    ('roles', 'code TEXT PRIMARY KEY,name TEXT NOT NULL'),
    ('permissions', 'code TEXT PRIMARY KEY,name TEXT NOT NULL'),
    ('role_permissions', 'role_code TEXT NOT NULL,permission_code TEXT NOT NULL,PRIMARY KEY(role_code,permission_code)'),
    ('users', 'id {pk},tenant_id INTEGER NOT NULL,username TEXT NOT NULL,role_code TEXT NOT NULL,password_hash TEXT,is_active INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,username)'),
    ('owners', 'id {pk},tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,name TEXT NOT NULL,phone TEXT,owner_type TEXT NOT NULL DEFAULT \'业主\''),
    ('charge_targets', 'id {pk},tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,owner_id INTEGER,building TEXT NOT NULL,unit TEXT,room_number TEXT NOT NULL,category TEXT NOT NULL,area REAL NOT NULL DEFAULT 0,unit_price_override REAL,UNIQUE(tenant_id,project_id,building,unit,room_number)'),
    ('fee_types', 'id {pk},tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,name TEXT NOT NULL,unit_price REAL NOT NULL DEFAULT 0,billing_mode TEXT NOT NULL DEFAULT \'area\',UNIQUE(tenant_id,project_id,name)'),
    ('bills', 'id {pk},tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,charge_target_id INTEGER NOT NULL,fee_type_id INTEGER NOT NULL,bill_number TEXT NOT NULL,billing_period TEXT NOT NULL,service_start TEXT,service_end TEXT,amount REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT \'pending_review\',UNIQUE(tenant_id,project_id,bill_number)'),
    ('payments', 'id {pk},tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,bill_id INTEGER NOT NULL,amount_paid REAL NOT NULL,method TEXT,idempotency_key TEXT,receipt_number TEXT,UNIQUE(tenant_id,idempotency_key)'),
    ('imports', 'id {pk},tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,import_type TEXT NOT NULL,status TEXT NOT NULL,original_name TEXT,storage_key TEXT,file_size INTEGER,content_type TEXT,summary_json TEXT NOT NULL DEFAULT \'{}\''),
    ('backup_records', 'id {pk},tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,backup_id TEXT NOT NULL,status TEXT NOT NULL,created_by INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(tenant_id,backup_id)'),
    ('restore_drills', 'id {pk},tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,backup_id TEXT NOT NULL,scope TEXT NOT NULL,status TEXT NOT NULL,created_by INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP'),
    ('audit_logs', 'id {pk},tenant_id INTEGER NOT NULL,project_id INTEGER NOT NULL,user_id INTEGER,action TEXT NOT NULL,entity_type TEXT,entity_id INTEGER,detail_json TEXT NOT NULL DEFAULT \'{}\''),
]


def is_postgres(dialect):
    return str(dialect or '').startswith('postgres')


def schema_statements(dialect):
    pk = 'SERIAL PRIMARY KEY' if is_postgres(dialect) else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    return [f"CREATE TABLE IF NOT EXISTS {table}({columns.replace('{pk}', pk)})" for table, columns in TABLES]


def alter_statements(dialect):
    if is_postgres(dialect):
        return [
            "ALTER TABLE fee_types ADD COLUMN IF NOT EXISTS billing_mode TEXT NOT NULL DEFAULT 'area'",
            "ALTER TABLE charge_targets ADD COLUMN IF NOT EXISTS unit_price_override REAL",
        ]
    return [
        "ALTER TABLE fee_types ADD COLUMN billing_mode TEXT NOT NULL DEFAULT 'area'",
        "ALTER TABLE charge_targets ADD COLUMN unit_price_override REAL",
    ]


def upsert_named_sql(table, dialect):
    if is_postgres(dialect):
        return f"INSERT INTO {table}(code,name) VALUES(:code,:name) ON CONFLICT(code) DO UPDATE SET name=EXCLUDED.name"
    return f"INSERT OR REPLACE INTO {table}(code,name) VALUES(:code,:name)"


def grant_permission_sql(dialect):
    if is_postgres(dialect):
        return "INSERT INTO role_permissions(role_code,permission_code) VALUES(:role_code,:permission_code) ON CONFLICT(role_code,permission_code) DO NOTHING"
    return "INSERT OR IGNORE INTO role_permissions(role_code,permission_code) VALUES(:role_code,:permission_code)"


def insert_id_sql(sql, dialect):
    clean = str(sql).rstrip()
    if is_postgres(dialect) and 'RETURNING id' not in clean.upper():
        return clean + ' RETURNING id'
    return clean


def inserted_id(result, dialect):
    if is_postgres(dialect):
        return int(result.scalar_one())
    return int(result.lastrowid)
