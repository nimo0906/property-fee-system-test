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
    "scripts/saas_customer_acceptance_signoff_check.py",
    "scripts/saas_commercial_launch_report_check.py",
    "scripts/saas_formal_launch_report_check.py",
    "scripts/saas_operator_one_page_runbook_check.py",
    "scripts/saas_day1_operations_checklist_check.py",
    "scripts/saas_day7_stability_review_check.py",
    "scripts/saas_next_phase_decision_check.py",
    "scripts/saas_next_phase_issue_backlog_check.py",
    "scripts/saas_license_cloud_boundary_check.py",
    "scripts/saas_license_cloud_management_check.py",
    "scripts/saas_license_status_integration_check.py",
    "scripts/saas_license_enforcement_check.py",
    "scripts/saas_license_enforcement_audit_check.py",
    "scripts/saas_license_seat_limit_check.py",
    "scripts/saas_license_ops_page_check.py",
    "scripts/saas_license_tenant_binding_check.py",
    "scripts/saas_license_binding_page_check.py",
    "scripts/saas_license_binding_persistence_check.py",
    "scripts/saas_license_binding_backup_check.py",
    "scripts/saas_license_binding_runbook_check.py",
    "scripts/saas_production_deployment_rehearsal_check.py",
    "scripts/saas_production_precheck.py",
    "scripts/saas_first_tenant_wizard_check.py",
    "scripts/saas_first_tenant_delivery_loop_check.py",
    "scripts/saas_first_tenant_acceptance_record_check.py",
    "scripts/saas_first_tenant_acceptance_export_check.py",
    "scripts/saas_first_tenant_delivery_package_check.py",
    "scripts/saas_tenant_business_template_check.py",
    "scripts/saas_tenant_business_config_check.py",
    "scripts/saas_tenant_business_config_page_check.py",
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
