#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check repository bootstrap SQL is PostgreSQL-compatible."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.saas_repository_schema import alter_statements, grant_permission_sql, schema_statements, upsert_named_sql


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    schema = '\n'.join(schema_statements('postgresql'))
    upserts = '\n'.join([upsert_named_sql('roles', 'postgresql'), upsert_named_sql('permissions', 'postgresql'), grant_permission_sql('postgresql')])
    alters = '\n'.join(alter_statements('postgresql'))
    require('AUTOINCREMENT' not in schema, 'postgres schema contains AUTOINCREMENT')
    require('SERIAL PRIMARY KEY' in schema, 'postgres schema missing SERIAL primary key')
    require('INSERT OR REPLACE' not in upserts, 'postgres upsert contains SQLite replace syntax')
    require('INSERT OR IGNORE' not in upserts, 'postgres upsert contains SQLite ignore syntax')
    require('ON CONFLICT' in upserts, 'postgres upsert missing ON CONFLICT')
    require('ADD COLUMN IF NOT EXISTS billing_mode' in alters, 'postgres alter not idempotent')
    require('ADD COLUMN IF NOT EXISTS unit_price_override' in alters, 'postgres alter missing unit price field')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py']:
        require('scripts/saas_postgres_repository_compat_check.py' in (ROOT / path).read_text(encoding='utf-8'), f'{path} missing postgres compat check')
    print('saas_postgres_repository_compat_check: PASS')


if __name__ == '__main__':
    main()
