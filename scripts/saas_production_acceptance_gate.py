#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-command production acceptance gate after SaaS deployment."""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(script, args=None):
    args = args or []
    rel = f'scripts/{script}'
    printable = ' '.join([rel, *args]).strip()
    print(f'RUN {printable}')
    result = subprocess.run(
        [PYTHON, str(ROOT / rel), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=120,
    )
    print(result.stdout, end='')
    if result.returncode != 0:
        raise SystemExit(f'FAIL {rel}')
    print(f'PASS {rel}')


def plan(dry_run, local_testclient, env_file, base_url):
    env_args = ['--dry-run'] if dry_run or local_testclient else ['--env-file', env_file]
    runtime_args = ['--dry-run'] if dry_run or local_testclient else []
    smoke_args = ['--dry-run'] if dry_run else ['--local-testclient'] if local_testclient else ['--base-url', base_url]
    return [
        ('saas_production_env_file_check.py', env_args),
        ('saas_production_precheck.py', ['--dry-run']),
        ('saas_production_runtime_check.py', runtime_args),
        ('saas_production_first_tenant_smoke.py', smoke_args),
        ('saas_isolation_evidence.py', []),
        ('saas_release_evidence.py', []),
    ]


def main():
    parser = argparse.ArgumentParser(description='Run production SaaS acceptance gate.')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--local-testclient', action='store_true')
    parser.add_argument('--env-file', default='.env')
    parser.add_argument('--base-url', default='https://your-domain.example.com')
    args = parser.parse_args()
    for script, script_args in plan(args.dry_run, args.local_testclient, args.env_file, args.base_url):
        run(script, script_args)
    print('saas_production_acceptance_gate: PASS')


if __name__ == '__main__':
    main()
