#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS tenant isolation evidence detail assets."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "saas_isolation_evidence.py"
REPORT = ROOT / "release" / "saas-isolation-evidence.md"
RELEASE_REPORT = ROOT / "release" / "saas-release-evidence.md"


def test_isolation_evidence_script_generates_detail_report():
    assert SCRIPT.exists()
    if REPORT.exists():
        REPORT.unlink()
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True, check=False, timeout=90
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "saas_isolation_evidence: PASS" in result.stdout
    assert REPORT.exists()
    text = REPORT.read_text(encoding="utf-8")
    for item in [
        "SaaS 租户隔离证据明细",
        "A样例公司",
        "B样例公司",
        "收费对象隔离",
        "账单隔离",
        "收款隔离",
        "报表隔离",
        "审计日志隔离",
        "备份恢复隔离",
        "客户上传数据与系统自身数据隔离",
        "tenant-files",
        "system-files",
        "PASS",
    ]:
        assert item in text
    for forbidden in ["POSTGRES_PASSWORD=", "APP_SECRET_KEY=", "/Users/nimo", "真实客户"]:
        assert forbidden not in text


def test_release_gate_runs_isolation_evidence_before_release_evidence():
    gate = (ROOT / "scripts" / "saas_release_gate.py").read_text(encoding="utf-8")
    assert "scripts/saas_isolation_evidence.py" in gate
    assert gate.index("scripts/saas_isolation_evidence.py") < gate.index("scripts/saas_release_evidence.py")


def test_release_evidence_report_links_isolation_detail():
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, text=True, capture_output=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "saas_release_evidence.py")], cwd=ROOT, check=True, text=True, capture_output=True)
    text = RELEASE_REPORT.read_text(encoding="utf-8")
    assert "release/saas-isolation-evidence.md" in text
    assert "租户隔离证据明细" in text


def test_isolation_evidence_is_registered_and_visible():
    for path in [
        "server/saas_deploy.py",
        "server/saas_deploy_pages.py",
        "server/saas_acceptance_pages.py",
    ]:
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "scripts/saas_isolation_evidence.py" in text
        assert "租户隔离证据明细" in text
