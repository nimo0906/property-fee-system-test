#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check repository insert id handling is PostgreSQL-compatible."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.saas_repository_schema import insert_id_sql


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    require(insert_id_sql('INSERT INTO tenants(name) VALUES(:name)', 'postgresql').endswith(' RETURNING id'), 'postgres insert missing RETURNING id')
    require(insert_id_sql('INSERT INTO tenants(name) VALUES(:name)', 'sqlite') == 'INSERT INTO tenants(name) VALUES(:name)', 'sqlite insert should not change')
    offenders = []
    for path in (ROOT / 'server').glob('saas_repository*.py'):
        if path.name == 'saas_repository_schema.py':
            continue
        if 'lastrowid' in path.read_text(encoding='utf-8'):
            offenders.append(str(path.relative_to(ROOT)))
    require(not offenders, 'repository direct lastrowid usage: ' + ', '.join(offenders))
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py']:
        require('scripts/saas_postgres_insert_id_check.py' in (ROOT / path).read_text(encoding='utf-8'), f'{path} missing insert id check')
    print('saas_postgres_insert_id_check: PASS')


if __name__ == '__main__':
    main()
