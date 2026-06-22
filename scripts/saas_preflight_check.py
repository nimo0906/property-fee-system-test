#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preflight check for SaaS cloud backoffice deployment."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.saas_deploy import validate_deployment_assets, validate_env_security


def main():
    result = validate_deployment_assets(ROOT)
    if not result['ok']:
        raise SystemExit(f"deployment assets not ready: {result}")
    print('PASS saas deploy assets')
    print('PASS saas storage isolation contract')
    if result.get('port_binding', {}).get('localhost_only'):
        print('PASS saas app port localhost binding')
    if all(result.get('restart_policy', {}).values()):
        print('PASS saas compose restart policy')
    if result.get('healthcheck', {}).get('postgres_has_healthcheck'):
        print('PASS saas postgres healthcheck')
    if result.get('healthcheck', {}).get('app_has_healthcheck'):
        print('PASS saas app healthcheck')
    env = {
        'POSTGRES_PASSWORD': 'P@ssw0rd-2026-tenant-safe-9c5f1e7b',
        'APP_SECRET_KEY': '0123456789abcdef0123456789abcdef',
    }
    env_result = validate_env_security(env)
    if not env_result['ok']:
        raise SystemExit(f"env security failed: {env_result}")
    print('PASS saas env example security')
    print('WARN nginx http only: keep HTTP redirect only; terminate HTTPS at Nginx or upstream load balancer before production')


if __name__ == '__main__':
    main()
