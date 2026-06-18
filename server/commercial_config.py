#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commercial edition local setup and license enforcement helpers."""

import json
import os
from datetime import date, datetime
from pathlib import Path

from desktop_runtime import get_app_data_dir

DEFAULT_SETUP = {
    "company_name": "",
    "project_name": "",
    "default_billing_cycle": "monthly",
    "default_property_rate": "",
    "enable_commercial_billing": True,
    "enable_meter_reading": True,
    "enable_parking": False,
    "initialized": False,
}

BLOCKING_LICENSE_LABELS = {"已过期", "授权异常"}
PUBLIC_PATHS = ("/login", "/logout", "/register", "/static/")
LICENSE_PATHS = ("/license_status", "/commercial_license")
FIRST_RUN_PATHS = ("/first_run_guide", "/first_run_setup")


def setup_file_path(data_dir=None):
    base = Path(data_dir) if data_dir else get_app_data_dir()
    return base / "config" / "first_run.json"


def read_setup_config(data_dir=None):
    data = dict(DEFAULT_SETUP)
    path = setup_file_path(data_dir)
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update({k: v for k, v in loaded.items() if v is not None})
        except Exception as exc:
            data["load_error"] = str(exc)
    data["setup_file"] = str(path)
    data["initialized"] = bool(data.get("initialized") and data.get("company_name") and data.get("project_name"))
    return data


def save_setup_config(values, data_dir=None):
    data = dict(DEFAULT_SETUP)
    data.update({k: values.get(k, data.get(k)) for k in DEFAULT_SETUP})
    data["company_name"] = str(data.get("company_name") or "").strip()
    data["project_name"] = str(data.get("project_name") or "").strip()
    data["default_billing_cycle"] = str(data.get("default_billing_cycle") or "monthly")
    data["default_property_rate"] = str(data.get("default_property_rate") or "").strip()
    for key in ("enable_commercial_billing", "enable_meter_reading", "enable_parking"):
        data[key] = _as_bool(data.get(key))
    data["initialized"] = bool(data["company_name"] and data["project_name"])
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = setup_file_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    data["setup_file"] = str(path)
    return data


def should_force_first_run(path, user, data_dir=None):
    if _is_public_or_setup_path(path):
        return False
    if not user:
        return False
    if os.environ.get("PM_SKIP_FIRST_RUN") == "1":
        return False
    if os.environ.get("PM_ENFORCE_FIRST_RUN") != "1":
        return False
    return not read_setup_config(data_dir).get("initialized")


def license_blocks_access(status):
    return status.get("status_label") in BLOCKING_LICENSE_LABELS


def license_block_message(status):
    label = status.get("status_label") or "授权异常"
    expires = status.get("expires_at") or "未设置"
    return f"授权状态为{label}，到期日期：{expires}。请更新授权后再进入系统。"


def should_block_for_license(path, user, status):
    if _is_public_or_setup_path(path) or path in LICENSE_PATHS:
        return False
    if not user:
        return False
    return license_blocks_access(status)


def days_until_expiry(value):
    if not value:
        return None
    try:
        expires = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return (expires - date.today()).days


def _is_public_or_setup_path(path):
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in PUBLIC_PATHS + FIRST_RUN_PATHS)


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes", "on", "启用")
