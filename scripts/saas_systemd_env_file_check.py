#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check systemd production env file loading for SaaS deployment."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = 'scripts/saas_systemd_env_file_check.py'
ENV_FILE = '/opt/property-saas/.env'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def read(path):
    return path.read_text(encoding='utf-8') if path.exists() else ''


def check_systemd_service():
    service = read(ROOT / 'deploy/systemd/property-saas.service')
    require('EnvironmentFile=-/opt/property-saas/.env' in service, 'systemd service must load optional production env file')
    require('docker compose up -d' in service, 'systemd service must start docker compose')
    for forbidden in ['POSTGRES_PASSWORD=', 'APP_SECRET_KEY=', '/Users/nimo']:
        require(forbidden not in service, f'systemd service leaks forbidden content: {forbidden}')
    print('PASS systemd loads production env file')


def check_env_contract():
    env = read(ROOT / '.env.example')
    require('POSTGRES_PASSWORD' in env, 'env example missing POSTGRES_PASSWORD')
    require('APP_SECRET_KEY' in env, 'env example missing APP_SECRET_KEY')
    require('generate-postgres-password-with-openssl-rand-hex-32' in env, 'env example must use safe password instruction')
    require('generate-app-secret-with-openssl-rand-hex-32' in env, 'env example must use safe app secret instruction')
    print('PASS env example declares production secrets')


def check_gitignore():
    gitignore = read(ROOT / '.gitignore')
    require('.env' in gitignore, 'gitignore must exclude local .env')
    print('PASS local env is gitignored')


def check_registry():
    for path in [
        'scripts/saas_release_gate.py',
        'scripts/saas_release_evidence.py',
        'server/saas_deploy.py',
        'server/saas_commercial_readiness.py',
    ]:
        require(SCRIPT in read(ROOT / path), f'missing systemd env check registry in {path}')
    print('PASS release assets register systemd env check')


def main():
    check_systemd_service()
    check_env_contract()
    check_gitignore()
    check_registry()
    print('saas_systemd_env_file_check: PASS')


if __name__ == '__main__':
    main()
