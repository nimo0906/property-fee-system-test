#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production .env file validation for SaaS Linux/VPS delivery."""

import os
import stat
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from server.saas_app import create_app

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/saas_production_env_file_check.py'
SCRIPT_REF = 'scripts/saas_production_env_file_check.py'


def _write_env(path: Path, password='TenantSafePassword-2026-abcdef', secret='abcdef0123456789abcdef0123456789abcdef0123456789'):
    path.write_text('\n'.join([
        'POSTGRES_DB=property_saas',
        'POSTGRES_USER=property_saas_user',
        f'POSTGRES_PASSWORD={password}',
        f'APP_SECRET_KEY={secret}',
        'APP_BASE_URL=https://property.example.com',
        'SAAS_CUSTOMER_FILES_DIR=/var/lib/property-saas/tenants',
        'SAAS_SYSTEM_FILES_DIR=/var/lib/property-saas/system',
        'SAAS_BACKUP_DIR=/var/backups/property-saas',
        'SAAS_LOG_DIR=/var/log/property-saas',
        '',
    ]), encoding='utf-8')


def test_production_env_file_check_accepts_strong_env_and_masks_values(tmp_path):
    assert SCRIPT.exists(), 'missing production env file check script'
    env_file = tmp_path / '.env'
    _write_env(env_file)
    env_file.chmod(0o600)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--env-file', str(env_file)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for item in [
        'PASS production env file exists',
        'PASS production env file permissions',
        'PASS production env file required keys',
        'PASS production env file secret strength',
        'PASS production env file storage isolation',
        'saas_production_env_file_check: PASS',
    ]:
        assert item in result.stdout
    assert 'POSTGRES_PASSWORD: length=' in result.stdout
    assert 'APP_SECRET_KEY: length=' in result.stdout
    for forbidden in ['TenantSafePassword-2026-abcdef', 'abcdef0123456789abcdef', 'POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo']:
        assert forbidden not in result.stdout


def test_production_env_file_check_rejects_missing_weak_or_world_readable_env(tmp_path):
    missing = subprocess.run(
        [sys.executable, str(SCRIPT), '--env-file', str(tmp_path / '.env')],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert missing.returncode != 0
    assert 'missing production env file' in missing.stdout

    weak = tmp_path / 'weak.env'
    _write_env(weak, password='generate-postgres-password-with-openssl-rand-hex-32', secret='short')
    weak.chmod(0o600)
    weak_result = subprocess.run(
        [sys.executable, str(SCRIPT), '--env-file', str(weak)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert weak_result.returncode != 0
    assert 'FAIL production env file secret strength' in weak_result.stdout
    assert 'generate-postgres-password' not in weak_result.stdout

    wide = tmp_path / 'wide.env'
    _write_env(wide)
    wide.chmod(0o644)
    wide_result = subprocess.run(
        [sys.executable, str(SCRIPT), '--env-file', str(wide)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert wide_result.returncode != 0
    assert 'env file permissions too open' in wide_result.stdout


def test_production_env_file_check_is_registered_in_gate_evidence_and_pages():
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'scripts/saas_production_precheck.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert SCRIPT_REF in path.read_text(encoding='utf-8'), f'missing {SCRIPT_REF} in {path}'

    client = TestClient(create_app())
    login = client.post('/api/auth/login', json={
        'tenant_name': '现场环境校验物业',
        'project_name': '现场环境校验项目',
        'username': 'admin',
        'role_code': 'system_admin',
    })
    assert login.status_code == 200
    page = client.get('/backoffice/deploy-checklist')
    assert page.status_code == 200
    for item in [
        '生产 .env 现场校验',
        'scripts/saas_production_env_file_check.py',
        '不打印密钥原文',
        'chmod 600 .env',
    ]:
        assert item in page.text
    for hidden in ['POSTGRES_PASSWORD', 'APP_SECRET_KEY', 'tenant_id', 'project_id']:
        assert hidden not in page.text
