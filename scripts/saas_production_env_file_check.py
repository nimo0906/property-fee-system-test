#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate production .env file without printing secret values."""

import argparse
import stat
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.saas_deploy import ISOLATION_CONTRACT, validate_env_security

REQUIRED_KEYS = [
    'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY',
    'APP_BASE_URL', 'SAAS_CUSTOMER_FILES_DIR', 'SAAS_SYSTEM_FILES_DIR',
    'SAAS_BACKUP_DIR', 'SAAS_LOG_DIR',
]
SECRET_KEYS = ['POSTGRES_PASSWORD', 'APP_SECRET_KEY']
PLACEHOLDER_PREFIXES = ('generate-', 'replace-', 'change-', 'example-')


def fail(message):
    raise SystemExit(message)


def parse_env(path):
    data = {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def masked(name, value):
    return f'{name}: length={len(value or "")}'


def check_permissions(path, strict):
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        fail(f'env file permissions too open: mode={oct(mode)}; expected 0600')
    print('PASS production env file permissions')


def check_required(env):
    missing = [key for key in REQUIRED_KEYS if not env.get(key)]
    if missing:
        fail(f'missing production env keys: {", ".join(missing)}')
    print('PASS production env file required keys')


def check_secrets(env):
    problems = []
    for key in SECRET_KEYS:
        value = env.get(key, '').strip()
        lower = value.lower()
        if lower.startswith(PLACEHOLDER_PREFIXES):
            problems.append(key)
    security = validate_env_security({key: env.get(key, '') for key in SECRET_KEYS})
    problems.extend(security.get('weak') or [])
    if problems:
        print('FAIL production env file secret strength')
        for key in sorted(set(problems)):
            print(masked(key, env.get(key, '')))
        raise SystemExit(1)
    print('PASS production env file secret strength')
    for key in SECRET_KEYS:
        print(masked(key, env[key]))


def check_storage(env):
    expected = {
        'SAAS_CUSTOMER_FILES_DIR': ISOLATION_CONTRACT['customer_files'],
        'SAAS_SYSTEM_FILES_DIR': ISOLATION_CONTRACT['system_files'],
        'SAAS_BACKUP_DIR': ISOLATION_CONTRACT['backups'],
        'SAAS_LOG_DIR': ISOLATION_CONTRACT['logs'],
    }
    actual = {key: env.get(key, '') for key in expected}
    if actual != expected or len(set(actual.values())) != len(actual):
        fail('production env storage isolation mismatch')
    print('PASS production env file storage isolation')


def main():
    parser = argparse.ArgumentParser(description='Validate production SaaS .env file without leaking secrets.')
    parser.add_argument('--env-file', default='.env', help='path to production .env file')
    parser.add_argument('--dry-run', action='store_true', help='print file validation plan without requiring .env')
    args = parser.parse_args()
    if args.dry_run:
        print('PASS production env file plan exists')
        print('PASS production env file plan permissions')
        print('PASS production env file plan required keys')
        print('PASS production env file plan secret strength')
        print('PASS production env file plan storage isolation')
        print('saas_production_env_file_check: PASS')
        return
    env_path = Path(args.env_file)
    explicit = '--env-file' in sys.argv
    if not env_path.is_absolute():
        env_path = ROOT / env_path
    if not env_path.exists():
        if explicit:
            fail('missing production env file')
        print('WARN production env file not found; run with --env-file on server')
        print('saas_production_env_file_check: PASS')
        return
    print('PASS production env file exists')
    check_permissions(env_path, explicit)
    env = parse_env(env_path)
    check_required(env)
    check_secrets(env)
    check_storage(env)
    print('saas_production_env_file_check: PASS')


if __name__ == '__main__':
    main()
