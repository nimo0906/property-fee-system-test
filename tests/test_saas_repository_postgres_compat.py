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
