#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SaaS release evidence report assets."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "saas_release_evidence.py"
REPORT = ROOT / "release" / "saas-release-evidence.md"


def test_release_evidence_script_generates_sanitized_report():
    assert SCRIPT.exists()
    if REPORT.exists():
        REPORT.unlink()
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True, check=False, timeout=60
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "saas_release_evidence: PASS" in result.stdout
    assert REPORT.exists()
    text = REPORT.read_text(encoding="utf-8")
    for item in [
        "SaaS 云端商业版上线证据报告",
        "商业上线总门禁",
        "scripts/saas_release_gate.py",
        "scripts/saas_preflight_check.py",
        "scripts/saas_ops_check.py",
        "scripts/saas_acceptance_check.py",
        "scripts/saas_phase1_closure_check.py",
        "scripts/saas_demo_tenant_drill.py",
        "租户隔离",
        "客户上传数据与系统自身数据隔离",
        "部署资产",
        "后置范围",
        "业主端 H5 后置",
        "微信/支付宝真实支付后置",
        "授权云服务后台后置",
    ]:
        assert item in text
    for forbidden in ["POSTGRES_PASSWORD=", "APP_SECRET_KEY=", "/Users/nimo", ".env\n"]:
        assert forbidden not in text


def test_release_gate_runs_release_evidence_check():
    gate = (ROOT / "scripts" / "saas_release_gate.py").read_text(encoding="utf-8")
    assert "scripts/saas_release_evidence.py" in gate


def test_release_evidence_is_registered_and_visible():
    deploy = (ROOT / "server" / "saas_deploy.py").read_text(encoding="utf-8")
    deploy_page = (ROOT / "server" / "saas_deploy_pages.py").read_text(encoding="utf-8")
    acceptance_page = (ROOT / "server" / "saas_acceptance_pages.py").read_text(encoding="utf-8")
    for text in [deploy, deploy_page, acceptance_page]:
        assert "scripts/saas_release_evidence.py" in text
    assert "上线证据报告" in deploy_page
    assert "上线证据报告" in acceptance_page
