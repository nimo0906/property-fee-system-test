#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 11 meter reading release gate.

Scope markers for tests and reviewers:
- module 11 meter reading
- tenant/project isolation
- previous/current/consumption
- confirmed reading to pending review bill
- water/electric fee mode
- release gate registration
"""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/test_saas_module11_meter_readings.py', '-q'],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(result.stdout, end='')
    if result.returncode:
        raise SystemExit(result.returncode)
    print('saas_module11_meter_reading_gate: PASS')


if __name__ == '__main__':
    main()
