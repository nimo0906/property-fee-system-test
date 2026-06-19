#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PostgreSQL-compatible repository bootstrap SQL."""

import subprocess
import sys
from pathlib import Path

from server.saas_repository_schema import alter_statements, grant_permission_sql, schema_statements, upsert_named_sql


def test_postgres_schema_statements_do_not_use_sqlite_only_autoincrement():
    sql = '\n'.join(schema_statements('postgresql'))
    assert 'AUTOINCREMENT' not in sql
    assert 'SERIAL PRIMARY KEY' in sql
    for table in ['tenants', 'projects', 'users', 'charge_targets', 'bills', 'payments']:
        assert f'CREATE TABLE IF NOT EXISTS {table}' in sql


def test_postgres_bootstrap_upserts_do_not_use_sqlite_insert_or_syntax():
    sql = '\n'.join([
        upsert_named_sql('roles', 'postgresql'),
        upsert_named_sql('permissions', 'postgresql'),
        grant_permission_sql('postgresql'),
    ])
    assert 'INSERT OR REPLACE' not in sql
    assert 'INSERT OR IGNORE' not in sql
    assert 'ON CONFLICT' in sql
    assert 'DO UPDATE SET' in sql
    assert 'DO NOTHING' in sql


def test_postgres_alter_statements_are_idempotent_without_aborting_transaction():
    sql = '\n'.join(alter_statements('postgresql'))
    assert 'ADD COLUMN IF NOT EXISTS billing_mode' in sql
    assert 'ADD COLUMN IF NOT EXISTS unit_price_override' in sql
    for field in ['owner_type', 'floor', 'shop_name', 'tenant_name', 'tenant_phone', 'payment_cycle', 'notes']:
        assert field in sql


def test_postgres_repository_compat_check_script_is_in_release_assets():
    script = 'scripts/saas_postgres_repository_compat_check.py'
    result = subprocess.run([sys.executable, script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
    assert result.returncode == 0, result.stdout
    for path in [
        'scripts/saas_release_gate.py',
        'scripts/saas_release_evidence.py',
        'server/saas_deploy.py',
        'server/saas_commercial_readiness.py',
    ]:
        assert script in Path(path).read_text(encoding='utf-8')


def test_postgres_baseline_schema_contains_saas_business_alignment_columns():
    from server.saas_schema import build_saas_postgres_schema

    sql = build_saas_postgres_schema()
    for field in ['owner_type', 'billing_mode', 'unit_price_override', 'floor', 'shop_name', 'tenant_name', 'tenant_phone', 'payment_cycle', 'notes']:
        assert field in sql


def test_saas_alignment_alembic_migration_is_idempotent_with_baseline_schema():
    text = Path('alembic/versions/0007_saas_charge_target_room_fields.py').read_text(encoding='utf-8')
    assert "down_revision = \"0006_saas_payment_receipts\"" in text
    assert 'ADD COLUMN IF NOT EXISTS owner_type' in text
    assert 'ADD COLUMN IF NOT EXISTS unit_price_override' in text
    assert 'ADD COLUMN IF NOT EXISTS billing_mode' in text
    for field in ['floor', 'shop_name', 'tenant_name', 'tenant_phone', 'payment_cycle', 'notes']:
        assert f'ADD COLUMN IF NOT EXISTS {field}' in text
