#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only local commercial license status helpers."""

import json
import os
from datetime import date, datetime
from pathlib import Path

from desktop_runtime import get_app_data_dir

DEFAULT_LICENSE = {
    "status": "trial",
    "edition": "试用版",
    "customer_name": "未绑定客户",
    "projects": 1,
    "seats": 3,
    "license_model": "annual",
    "device_limit": 3,
    "offline_grace_days": 7,
    "expires_at": "",
    "license_key": "",
    "notes": "当前为本地试用状态；正式商业版按年授权，默认3台设备，离线宽限期7天。",
}


def license_file_path(data_dir=None):
    base = Path(data_dir) if data_dir else get_app_data_dir()
    return base / "license" / "license.json"


def read_license_status(data_dir=None):
    data = dict(DEFAULT_LICENSE)
    path = license_file_path(data_dir)
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update({k: v for k, v in loaded.items() if v is not None})
        except Exception as exc:
            data["status"] = "invalid"
            data["notes"] = f"授权文件读取失败：{exc}"
    data.update(_env_overrides())
    data["license_file"] = str(path)
    data["device_limit"] = _as_int(data.get("device_limit"), 3)
    data["offline_grace_days"] = _as_int(data.get("offline_grace_days"), 7)
    data["is_expired"] = _is_expired(data.get("expires_at"))
    data["status_label"] = _status_label(data)
    data["license_model_label"] = _license_model_label(data.get("license_model"))
    data["access_blocked"] = data["status_label"] in ("已过期", "授权异常")
    data["masked_key"] = _mask_key(data.get("license_key", ""))
    return data


def _env_overrides():
    mapping = {
        "PM_LICENSE_STATUS": "status",
        "PM_LICENSE_EDITION": "edition",
        "PM_LICENSE_CUSTOMER": "customer_name",
        "PM_LICENSE_PROJECTS": "projects",
        "PM_LICENSE_SEATS": "seats",
        "PM_LICENSE_MODEL": "license_model",
        "PM_LICENSE_DEVICE_LIMIT": "device_limit",
        "PM_LICENSE_OFFLINE_GRACE_DAYS": "offline_grace_days",
        "PM_LICENSE_EXPIRES_AT": "expires_at",
        "PM_LICENSE_KEY": "license_key",
    }
    return {target: os.environ[name] for name, target in mapping.items() if os.environ.get(name)}


def _is_expired(value):
    if not value:
        return False
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date() < date.today()
    except ValueError:
        return False


def _status_label(data):
    status = str(data.get("status") or "trial").lower()
    if data.get("is_expired"):
        return "已过期"
    return {
        "active": "已授权",
        "trial": "试用中",
        "inactive": "未激活",
        "invalid": "授权异常",
    }.get(status, status or "试用中")


def _mask_key(value):
    text = str(value or "").strip()
    if len(text) <= 8:
        return "未配置" if not text else "****"
    return text[:4] + "****" + text[-4:]


def _license_model_label(value):
    return {"annual": "按年授权", "trial": "试用授权", "subscription": "订阅授权"}.get(str(value or "annual"), str(value or "按年授权"))


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
