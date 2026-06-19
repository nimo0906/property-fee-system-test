#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial readiness checker script."""

import subprocess
import sys


def test_commercial_readiness_check_script_passes():
    result = subprocess.run(
        [sys.executable, 'scripts/saas_commercial_readiness_check.py'],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'saas_commercial_readiness_check: PASS' in result.stdout
