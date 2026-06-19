#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deployment asset validation for Linux/VPS SaaS slice.

Includes 租户隔离证据明细 release evidence assets.
"""

REQUIRED_DEPLOY_FILES = (
    "docker-compose.yml",
    ".env.example",
    "deploy/nginx/property-saas.conf",
    "deploy/systemd/property-saas.service",
    "deploy/logrotate/property-saas",
    "scripts/saas_backup.sh",
    "scripts/saas_restore.sh",
    "scripts/saas_env_security_check.py",
    "scripts/saas_acceptance_check.py",
    "scripts/saas_preflight_check.py",
    "scripts/saas_ops_check.py",
    "scripts/saas_phase1_closure_check.py",
    "scripts/saas_legacy_gap_check.py",
    "scripts/saas_demo_tenant_drill.py",
    "scripts/saas_release_gate.py",
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
    "scripts/saas_fee_type_template_init_check.py",
    "scripts/saas_first_tenant_fee_init_delivery_check.py",
    "scripts/saas_first_tenant_acceptance_fee_review_check.py",
    "scripts/saas_first_tenant_acceptance_risk_warning_check.py",
    "scripts/saas_first_tenant_acceptance_risk_overview_check.py",
    "scripts/saas_first_tenant_acceptance_persistence_check.py",
    "scripts/saas_first_tenant_acceptance_backup_evidence_check.py",
    "scripts/saas_first_tenant_acceptance_backup_page_check.py",
    "scripts/saas_production_database_env_check.py",
    "scripts/saas_postgres_repository_compat_check.py",
    "scripts/saas_postgres_insert_id_check.py",
    "scripts/saas_systemd_env_file_check.py",
    "scripts/saas_production_deployment_commands_check.py",
    "scripts/saas_production_env_file_check.py",
    "scripts/saas_production_runtime_check.py",
    "scripts/saas_production_first_tenant_smoke.py",
    "scripts/saas_production_acceptance_gate.py",
    "scripts/saas_production_acceptance_result.py",
    "scripts/saas_production_acceptance_page_check.py",
    "scripts/saas_production_acceptance_evidence_summary_check.py",
    "scripts/saas_production_acceptance_evidence_download_check.py",
    "scripts/saas_production_acceptance_signoff_check.py",
    "scripts/saas_production_acceptance_signoff_history_check.py",
    "scripts/saas_production_acceptance_signoff_backup_check.py",
    "scripts/saas_production_acceptance_evidence_package_check.py",
    "scripts/saas_production_acceptance_evidence_package_precheck.py",
    "scripts/saas_production_delivery_overview_check.py",
    "scripts/saas_production_delivery_status_summary_check.py",
    "scripts/saas_production_delivery_action_links_check.py",
    "scripts/saas_production_delivery_refresh_actions_check.py",
    "scripts/saas_production_delivery_missing_evidence_details_check.py",
    "scripts/build_saas_formal_launch_report.py",
    "scripts/saas_isolation_evidence.py",
    "scripts/saas_release_evidence.py",
    "docs/saas-cloud-ops-runbook.md",
    "docs/saas-cloud-deployment-drill.md",
    "docs/saas-commercial-delivery-drill.md",
    "docs/saas-minimal-launch-package.md",
    "docs/saas-customer-acceptance-signoff.md",
    "docs/saas-commercial-launch-report.md",
    "docs/saas-operator-one-page-runbook.md",
    "docs/saas-day1-operations-checklist.md",
    "docs/saas-day7-stability-review.md",
    "docs/saas-next-phase-decision-checklist.md",
    "docs/saas-next-phase-issue-backlog.md",
    "docs/saas-license-cloud-service-boundary.md",
    "docs/saas-license-binding-ops-runbook.md",
    "docs/saas-production-deployment-rehearsal.md",
    "docs/saas-production-precheck.md",
    "docs/saas-production-deployment-commands.md",
    "release/saas-commercial-launch-report.docx",
    "release/saas-commercial-launch-report.pdf",
    "docs/saas-phase-1-closure-report.md",
    "docs/saas-legacy-business-migration-gap.md",
    "docs/saas-demo-tenant-drill.md",
)


ISOLATION_CONTRACT = {
    "customer_files": "/var/lib/property-saas/tenants",
    "system_files": "/var/lib/property-saas/system",
    "backups": "/var/backups/property-saas",
    "logs": "/var/log/property-saas",
}


WEAK_SECRET_VALUES = {
    "",
    "change-me",
    "password",
    "replace-with-random-password",
    "replace-with-32-byte-random-secret",
    "generate-with-openssl-rand-hex-32",
}


def validate_env_security(env):
    weak = []
    password = str(env.get("POSTGRES_PASSWORD", "")).strip()
    secret = str(env.get("APP_SECRET_KEY", "")).strip()
    if password.lower() in WEAK_SECRET_VALUES or len(password) < 24:
        weak.append("POSTGRES_PASSWORD")
    if secret.lower() in WEAK_SECRET_VALUES or len(secret) < 32:
        weak.append("APP_SECRET_KEY")
    return {"ok": not weak, "weak": weak}


def inspect_nginx_tls(config_text):
    has_https = "listen 443" in config_text and "ssl_certificate" in config_text
    has_http = "listen 80" in config_text
    status = "https" if has_https else "http_only" if has_http else "unknown"
    return {"status": status, "has_https": has_https, "has_http": has_http}


def inspect_compose_port_binding(compose_text):
    ports = []
    for line in str(compose_text or "").splitlines():
        stripped = line.strip().strip('"').strip("'")
        if stripped.startswith("-"):
            value = stripped[1:].strip().strip('"').strip("'")
            if value.endswith(":8000"):
                ports.append(value)
    localhost_only = bool(ports) and all(p.startswith("127.0.0.1:") for p in ports)
    return {"localhost_only": localhost_only, "ports": ports}


def inspect_compose_restart_policy(compose_text):
    text = str(compose_text or "")
    return {
        "postgres": "restart: unless-stopped" in text,
        "app": "restart: on-failure" in text,
    }


def inspect_compose_healthcheck(compose_text):
    text = str(compose_text or "")
    postgres_has = "healthcheck:" in text and "pg_isready" in text
    postgres_test = "pg_isready" if "pg_isready" in text else ""
    app_has = "http://127.0.0.1:8000/health" in text and "healthcheck:" in text
    app_test = "/health" if "/health" in text else ""
    return {"postgres_has_healthcheck": postgres_has, "postgres_test": postgres_test, "app_has_healthcheck": app_has, "app_test": app_test}


def validate_deployment_assets(root):
    files = []
    missing = []
    for name in REQUIRED_DEPLOY_FILES:
        path = root / name
        if path.exists():
            files.append(name)
        else:
            missing.append(name)
    env_secure = True
    if (root / ".env.example").exists():
        env_text = (root / ".env.example").read_text(encoding="utf-8")
        env_secure = "replace-with-random-password" not in env_text and "replace-with-32-byte-random-secret" not in env_text
    nginx_path = root / "deploy/nginx/property-saas.conf"
    nginx_tls = inspect_nginx_tls(nginx_path.read_text(encoding="utf-8")) if nginx_path.exists() else {"status": "missing", "has_https": False, "has_http": False}
    compose_path = root / "docker-compose.yml"
    compose_text = compose_path.read_text(encoding="utf-8") if compose_path.exists() else ""
    port_binding = inspect_compose_port_binding(compose_text) if compose_path.exists() else {"localhost_only": False, "ports": []}
    restart_policy = inspect_compose_restart_policy(compose_text)
    healthcheck = inspect_compose_healthcheck(compose_text)
    return {
        "ok": not missing and env_secure and port_binding["localhost_only"] and all(restart_policy.values()) and healthcheck["postgres_has_healthcheck"] and healthcheck["app_has_healthcheck"],
        "files": files,
        "missing": missing,
        "isolation": ISOLATION_CONTRACT,
        "env_example_secure": env_secure,
        "nginx_tls": nginx_tls,
        "port_binding": port_binding,
        "restart_policy": restart_policy,
        "healthcheck": healthcheck,
    }
