#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 13 merchant contract release gate.

Scope markers for tests and reviewers:
- module 13 merchant contract
- tenant/project isolation
- contract period rent property fee deposit
- contract amendment effective date
- confirmed amendment recalculates future bills
- release gate registration
"""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/test_saas_module13_merchant_contracts.py', '-q'],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(result.stdout, end='')
    if result.returncode:
        raise SystemExit(result.returncode)
    print('saas_module13_merchant_contract_gate: PASS')


if __name__ == '__main__':
    main()
