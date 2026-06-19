#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production database environment wires SaaS app to persistent repository."""

from pathlib import Path
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_first_tenant_acceptance_store import database_url_from_env


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    with tempfile.TemporaryDirectory() as td:
        old = os.environ.get('DATABASE_URL')
        os.environ['DATABASE_URL'] = f"sqlite:///{Path(td) / 'saas.sqlite3'}"
        try:
            client = TestClient(create_app())
            health = client.get('/health')
            require(health.status_code == 200, 'health failed')
            require(health.json().get('storage') == 'persistent', 'app did not use persistent repository')
        finally:
            if old is None:
                os.environ.pop('DATABASE_URL', None)
            else:
                os.environ['DATABASE_URL'] = old
    env = {
        'POSTGRES_USER': 'property_user',
        'POSTGRES_PASSWORD': 'needs encoding/with:symbols',
        'POSTGRES_DB': 'property_db',
        'POSTGRES_HOST': 'postgres',
    }
    url = database_url_from_env(env)
    require(url and url.startswith('postgresql://property_user:'), 'postgres url not built')
    require('needs encoding/with:symbols' not in url, 'plain password leaked in url')
    require('needs%20encoding%2Fwith%3Asymbols' in url, 'password not url encoded')
    for path in ['scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py', 'server/saas_deploy.py']:
        text = (ROOT / path).read_text(encoding='utf-8')
        require('scripts/saas_production_database_env_check.py' in text, f'{path} missing production database check')
    print('saas_production_database_env_check: PASS')


if __name__ == '__main__':
    main()
