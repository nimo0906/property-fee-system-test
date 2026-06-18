#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deployment asset validation for Linux/VPS SaaS slice."""

REQUIRED_DEPLOY_FILES = (
    "docker-compose.yml",
    ".env.example",
    "deploy/nginx/property-saas.conf",
    "deploy/systemd/property-saas.service",
    "scripts/saas_backup.sh",
    "scripts/saas_restore.sh",
    "scripts/saas_acceptance_check.py",
    "scripts/saas_preflight_check.py",
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
    return {
        "ok": not missing and env_secure,
        "files": files,
        "missing": missing,
        "isolation": ISOLATION_CONTRACT,
        "env_example_secure": env_secure,
        "nginx_tls": nginx_tls,
    }
