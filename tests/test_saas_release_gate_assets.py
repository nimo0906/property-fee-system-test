#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS commercial release gate assets."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "saas_release_gate.py"
RUNBOOK = ROOT / "docs" / "saas-cloud-ops-runbook.md"


def test_release_gate_script_passes_and_runs_all_required_checks():
    assert SCRIPT.exists()
    env = os.environ.copy()
    env.update({
        "POSTGRES_PASSWORD": "P@ssw0rd-2026-tenant-safe-9c5f1e7b",
        "APP_SECRET_KEY": "0123456789abcdef0123456789abcdef0123456789abcdef",
    })
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True, check=False, timeout=180, env=env
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for item in [
        "RUN scripts/saas_env_security_check.py",
        "RUN scripts/saas_preflight_check.py",
        "RUN scripts/saas_ops_check.py",
        "RUN scripts/saas_acceptance_check.py",
        "RUN scripts/saas_phase1_closure_check.py",
        "RUN scripts/saas_demo_tenant_drill.py",
        "saas_release_gate: PASS",
    ]:
        assert item in result.stdout


def test_release_gate_is_registered_as_deploy_asset():
    deploy = (ROOT / "server" / "saas_deploy.py").read_text(encoding="utf-8")
    assert "scripts/saas_release_gate.py" in deploy


def test_deploy_and_acceptance_pages_show_release_gate_command():
    for path in ["server/saas_deploy_pages.py", "server/saas_acceptance_pages.py"]:
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "scripts/saas_release_gate.py" in text
        assert "商业上线总门禁" in text


def test_ops_runbook_documents_release_gate():
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "商业上线总门禁" in text
    assert "scripts/saas_release_gate.py" in text
    for item in [
        "scripts/saas_preflight_check.py",
        "scripts/saas_ops_check.py",
        "scripts/saas_acceptance_check.py",
        "scripts/saas_phase1_closure_check.py",
        "scripts/saas_demo_tenant_drill.py",
    ]:
        assert item in text
