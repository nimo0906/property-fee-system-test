#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""systemd production environment file loading for SaaS deployment."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / 'deploy/systemd/property-saas.service'
CHECK = ROOT / 'scripts/saas_systemd_env_file_check.py'


def test_systemd_service_loads_production_env_file_without_secret_leaks():
    text = SERVICE.read_text(encoding='utf-8')
    assert 'EnvironmentFile=-/opt/property-saas/.env' in text
    assert '/opt/property-saas/.env' in text
    assert 'docker compose up -d' in text
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo']:
        assert forbidden not in text


def test_systemd_env_file_check_script_is_registered_and_sanitized():
    assert CHECK.exists(), 'missing systemd env file check script'
    result = subprocess.run(
        [sys.executable, str(CHECK)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    for item in [
        'PASS systemd loads production env file',
        'PASS env example declares production secrets',
        'PASS local env is gitignored',
        'PASS release assets register systemd env check',
        'saas_systemd_env_file_check: PASS',
    ]:
        assert item in result.stdout
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo']:
        assert forbidden not in result.stdout


def test_systemd_env_file_check_is_visible_in_release_gate_evidence_and_readiness():
    script = 'scripts/saas_systemd_env_file_check.py'
    for path in [
        ROOT / 'scripts/saas_release_gate.py',
        ROOT / 'scripts/saas_release_evidence.py',
        ROOT / 'server/saas_deploy.py',
        ROOT / 'server/saas_commercial_readiness.py',
    ]:
        assert script in path.read_text(encoding='utf-8'), f'missing {script} in {path}'
