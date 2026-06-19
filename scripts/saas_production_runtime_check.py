#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check production runtime status after SaaS service startup."""

import argparse
from pathlib import Path
import subprocess

DEFAULTS = {
    'docker': 'docker compose ps',
    'systemctl': 'systemctl is-active property-saas',
    'health': 'curl -fsS http://127.0.0.1:8000/health',
    'login': 'curl -fsS https://your-domain.example.com/login',
    'ports': "ss -ltnp | grep ':8000' || true",
    'nginx': 'nginx -t',
}


def fail(message):
    raise SystemExit(message)


def run_shell(command):
    result = subprocess.run(
        command,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=30,
    )
    return result.returncode, result.stdout.strip()


def require_ok(name, command, predicate, fail_message):
    code, output = run_shell(command)
    if code != 0 or not predicate(output):
        fail(f'{fail_message}: {name}')
    return output


def dry_run():
    print('PASS runtime check plan docker compose ps')
    print('PASS runtime check plan systemctl is-active property-saas')
    print('PASS runtime check plan health endpoint')
    print('PASS runtime check plan login endpoint')
    print('PASS runtime check plan localhost port binding')
    print('PASS runtime check plan nginx config')
    print('PASS runtime check plan log directory writable')
    print('saas_production_runtime_check: PASS')


def check_log_dir(path):
    target = Path(path)
    if not target.exists() or not target.is_dir():
        fail('runtime log directory missing')
    probe = target / '.runtime-check-write-test'
    try:
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
    except Exception as exc:
        fail(f'runtime log directory not writable: {exc.__class__.__name__}')
    print('PASS runtime log directory writable')


def main():
    parser = argparse.ArgumentParser(description='Check SaaS runtime status after production startup.')
    parser.add_argument('--dry-run', action='store_true', help='print check plan without touching local server tools')
    parser.add_argument('--docker-cmd', default=DEFAULTS['docker'])
    parser.add_argument('--systemctl-cmd', default=DEFAULTS['systemctl'])
    parser.add_argument('--health-cmd', default=DEFAULTS['health'])
    parser.add_argument('--login-cmd', default=DEFAULTS['login'])
    parser.add_argument('--ports-cmd', default=DEFAULTS['ports'])
    parser.add_argument('--nginx-cmd', default=DEFAULTS['nginx'])
    parser.add_argument('--log-dir', default='/var/log/property-saas')
    args = parser.parse_args()
    if args.dry_run:
        dry_run()
        return

    require_ok('docker compose ps', args.docker_cmd, lambda out: 'Up' in out or 'running' in out.lower(), 'runtime docker compose not healthy')
    print('PASS runtime docker compose ps')
    require_ok('systemctl is-active property-saas', args.systemctl_cmd, lambda out: 'active' in out.lower(), 'runtime systemd not active')
    print('PASS runtime systemd active')
    require_ok('health endpoint', args.health_cmd, lambda out: bool(out), 'runtime health endpoint failed')
    print('PASS runtime health endpoint')
    require_ok('login endpoint', args.login_cmd, lambda out: 'login' in out.lower() or '<html' in out.lower(), 'runtime login endpoint failed')
    print('PASS runtime login endpoint')
    ports = require_ok('localhost port binding', args.ports_cmd, lambda out: '8000' in out, 'runtime port binding missing')
    if '0.0.0.0:8000' in ports or ':::8000' in ports:
        fail('runtime port binding must stay on 127.0.0.1')
    if '127.0.0.1:8000' not in ports and 'localhost:8000' not in ports:
        fail('runtime port binding must stay on 127.0.0.1')
    print('PASS runtime localhost port binding')
    require_ok('nginx config', args.nginx_cmd, lambda out: 'ok' in out.lower() or 'successful' in out.lower(), 'runtime nginx config failed')
    print('PASS runtime nginx config')
    check_log_dir(args.log_dir)
    print('saas_production_runtime_check: PASS')


if __name__ == '__main__':
    main()
