#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-command production deployment precheck for SaaS commercial delivery."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.saas_deploy import ISOLATION_CONTRACT, validate_deployment_assets

REQUIRED_ASSETS = [
    'docker-compose.yml', '.env.example', 'deploy/nginx/property-saas.conf',
    'deploy/systemd/property-saas.service', 'deploy/logrotate/property-saas',
    'scripts/saas_backup.sh', 'scripts/saas_restore.sh',
    'scripts/saas_release_gate.py', 'scripts/saas_release_evidence.py',
    'scripts/saas_isolation_evidence.py', 'scripts/saas_license_binding_backup_check.py',
    'docs/saas-production-precheck.md', 'release/saas-release-evidence.md',
    'release/saas-isolation-evidence.md',
]


def fail(message):
    raise SystemExit(message)


def require(condition, message):
    if not condition:
        fail(message)


def read(path):
    return path.read_text(encoding='utf-8') if path.exists() else ''


def check_assets(root):
    missing = [name for name in REQUIRED_ASSETS if not (root / name).exists()]
    require(not missing, f'missing production precheck assets: {missing}')
    print('PASS production precheck assets')


def check_environment_contract(root):
    env_example = read(root / '.env.example')
    require('POSTGRES_PASSWORD' in env_example, 'env example missing database password key')
    require('APP_SECRET_KEY' in env_example, 'env example missing app secret key')
    require('.env' in read(root / '.gitignore'), 'gitignore must exclude .env')
    print('PASS production precheck environment contract')


def check_deployment_contract(root):
    result = validate_deployment_assets(root)
    require(result.get('port_binding', {}).get('localhost_only'), 'app port must bind localhost only')
    print('PASS production precheck ports')
    isolation = result.get('isolation') or {}
    require(isolation == ISOLATION_CONTRACT, 'storage isolation contract changed')
    require(len(set(isolation.values())) == len(isolation), 'storage directories must be distinct')
    print('PASS production precheck storage directories')
    restart = result.get('restart_policy') or {}
    health = result.get('healthcheck') or {}
    require(all(restart.values()), 'compose restart policy missing')
    require(health.get('postgres_has_healthcheck'), 'postgres healthcheck missing')
    require(health.get('app_has_healthcheck'), 'app healthcheck missing')
    print('PASS production precheck docker compose')
    nginx = result.get('nginx_tls') or {}
    require(nginx.get('has_http') or nginx.get('has_https'), 'nginx listener missing')
    print('PASS production precheck nginx tls')


def check_ops_assets(root):
    service = read(root / 'deploy/systemd/property-saas.service')
    require('docker compose' in service or 'docker-compose' in service, 'systemd service must manage compose')
    print('PASS production precheck systemd')
    logrotate = read(root / 'deploy/logrotate/property-saas')
    require('/var/log/property-saas' in logrotate, 'logrotate must cover SaaS logs')
    print('PASS production precheck logrotate')
    backup = read(root / 'scripts/saas_backup.sh')
    restore = read(root / 'scripts/saas_restore.sh')
    require('metadata.json' in backup, 'backup script must write metadata')
    require('verify-metadata' in restore, 'restore script must support metadata verification')
    print('PASS production precheck backup restore assets')


def check_license_and_evidence(root):
    binding_doc = read(root / 'docs/saas-license-binding-ops-runbook.md')
    require('system/license_bindings/tenant_license_bindings.json' in binding_doc, 'license binding path missing')
    require('scripts/saas_license_binding_backup_check.py' in binding_doc, 'license binding backup check missing')
    print('PASS production precheck license binding assets')
    gate = read(root / 'scripts/saas_release_gate.py')
    release = root / 'release/saas-release-evidence.md'
    isolation = root / 'release/saas-isolation-evidence.md'
    require('scripts/saas_production_precheck.py' in gate, 'release gate missing production precheck')
    require(release.exists() and isolation.exists(), 'release evidence files missing')
    print('PASS production precheck evidence assets')


def main():
    parser = argparse.ArgumentParser(description='Run SaaS production deployment precheck.')
    parser.add_argument('--dry-run', action='store_true', help='read-only mode for CI and local verification')
    parser.parse_args()
    check_assets(ROOT)
    check_environment_contract(ROOT)
    check_deployment_contract(ROOT)
    check_ops_assets(ROOT)
    check_license_and_evidence(ROOT)
    print('saas_production_precheck: PASS')


if __name__ == '__main__':
    main()
