#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PostgreSQL-compatible inserted id handling for SaaS repository writes."""

import subprocess
import sys
from pathlib import Path

from server.saas_repository_schema import insert_id_sql


def test_postgres_insert_id_sql_appends_returning_id():
    sql = insert_id_sql('INSERT INTO tenants(name) VALUES(:name)', 'postgresql')
    assert sql.endswith(' RETURNING id')
    assert 'RETURNING id' in sql


def test_sqlite_insert_id_sql_keeps_original_insert():
    original = 'INSERT INTO tenants(name) VALUES(:name)'
    assert insert_id_sql(original, 'sqlite') == original


def test_saas_repository_modules_do_not_call_result_lastrowid_directly():
    files = list(Path('server').glob('saas_repository*.py'))
    offenders = []
    for path in files:
        if path.name == 'saas_repository_schema.py':
            continue
        if 'lastrowid' in path.read_text(encoding='utf-8'):
            offenders.append(str(path))
    assert offenders == []


def test_postgres_insert_id_check_script_is_in_release_assets():
    script = 'scripts/saas_postgres_insert_id_check.py'
    result = subprocess.run([sys.executable, script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
    assert result.returncode == 0, result.stdout
    for path in [
        'scripts/saas_release_gate.py',
        'scripts/saas_release_evidence.py',
        'server/saas_deploy.py',
        'server/saas_commercial_readiness.py',
    ]:
        assert script in Path(path).read_text(encoding='utf-8')
