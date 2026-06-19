#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production database environment wiring for SaaS app startup."""

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app
from server.saas_first_tenant_acceptance_store import database_url_from_env


def test_create_app_uses_database_url_from_environment(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'saas.sqlite3'}"
    monkeypatch.setenv('DATABASE_URL', db_url)
    client = TestClient(create_app())
    health = client.get('/health')
    assert health.status_code == 200
    assert health.json()['storage'] == 'persistent'
    assert client.app.state.repository is not None


def test_database_url_can_be_built_from_postgres_env_without_leaking_plain_secret(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('POSTGRES_USER', 'property_user')
    monkeypatch.setenv('POSTGRES_PASSWORD', 'needs encoding/with:symbols')
    monkeypatch.setenv('POSTGRES_DB', 'property_db')
    monkeypatch.setenv('POSTGRES_HOST', 'postgres')
    url = database_url_from_env()
    assert url.startswith('postgresql://property_user:')
    assert 'postgres:5432/property_db' in url
    assert 'needs encoding/with:symbols' not in url
    assert 'needs%20encoding%2Fwith%3Asymbols' in url


def test_production_database_env_check_script_is_in_release_assets():
    script = 'scripts/saas_production_database_env_check.py'
    result = subprocess.run([sys.executable, script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
    assert result.returncode == 0, result.stdout
    for path in [
        'scripts/saas_release_gate.py',
        'scripts/saas_release_evidence.py',
        'server/saas_deploy.py',
        'server/saas_commercial_readiness.py',
    ]:
        assert script in Path(path).read_text(encoding='utf-8')
