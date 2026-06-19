#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial release gate for SaaS cloud backoffice."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
CHECKS = [
    "scripts/saas_env_security_check.py",
    "scripts/saas_preflight_check.py",
    "scripts/saas_ops_check.py",
    "scripts/saas_acceptance_check.py",
    "scripts/saas_phase1_closure_check.py",
    "scripts/saas_legacy_gap_check.py",
    "scripts/saas_demo_tenant_drill.py",
    "scripts/saas_commercial_readiness_check.py",
    "scripts/saas_deployment_drill_check.py",
    "scripts/saas_commercial_delivery_drill.py",
    "scripts/saas_commercial_delivery_drill_check.py",
    "scripts/saas_minimal_launch_package_check.py",
    "scripts/saas_isolation_evidence.py",
    "scripts/saas_release_evidence.py",
]


def run_check(script):
    print(f"RUN {script}")
    result = subprocess.run(
        [PYTHON, str(ROOT / script)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        raise SystemExit(f"FAIL {script}")
    print(f"PASS {script}")


def main():
    for script in CHECKS:
        run_check(script)
    print("saas_release_gate: PASS")


if __name__ == "__main__":
    main()
