#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS production environment security check assets."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "saas_env_security_check.py"


def run_script(env):
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True, check=False, timeout=30, env=merged
    )


def test_env_security_script_rejects_missing_or_weak_values_without_reading_dotenv():
    assert SCRIPT.exists()
    result = run_script({"POSTGRES_PASSWORD": "short", "APP_SECRET_KEY": "weak"})
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "POSTGRES_PASSWORD" in output
    assert "APP_SECRET_KEY" in output
    assert ".env" not in output


def test_env_security_script_passes_with_strong_runtime_environment():
    result = run_script({
        "POSTGRES_PASSWORD": "P@ssw0rd-2026-tenant-safe-9c5f1e7b",
        "APP_SECRET_KEY": "0123456789abcdef0123456789abcdef0123456789abcdef",
    })
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS saas production env security" in result.stdout
    assert "POSTGRES_PASSWORD=" not in result.stdout
    assert "APP_SECRET_KEY=" not in result.stdout


def test_env_security_is_registered_in_release_gate_and_deploy_assets():
    gate = (ROOT / "scripts" / "saas_release_gate.py").read_text(encoding="utf-8")
    deploy = (ROOT / "server" / "saas_deploy.py").read_text(encoding="utf-8")
    assert "scripts/saas_env_security_check.py" in gate
    assert "scripts/saas_env_security_check.py" in deploy
    assert gate.index("scripts/saas_env_security_check.py") < gate.index("scripts/saas_preflight_check.py")


def test_env_security_is_visible_in_pages_and_runbook():
    for path in [
        "server/saas_deploy_pages.py",
        "server/saas_acceptance_pages.py",
        "docs/saas-cloud-ops-runbook.md",
        "scripts/saas_release_evidence.py",
    ]:
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "scripts/saas_env_security_check.py" in text
        assert "生产环境变量安全检查" in text
