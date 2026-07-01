#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers for keeping the desktop launcher and local service in sync."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


STATE_FILE_NAME = "desktop_service.json"


def get_state_path(data_dir):
    return Path(data_dir) / "logs" / STATE_FILE_NAME


def write_service_state(data_dir, port, url, pid=None):
    path = get_state_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "pid": pid or os.getpid(),
        "port": int(port),
        "url": url,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_service_state(data_dir):
    path = get_state_path(data_dir)
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict) or not state.get("url"):
        return None
    return state


def build_health_url(url):
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/health", "", "", ""))


def is_service_healthy(url, timeout=1.0):
    try:
        with urllib.request.urlopen(build_health_url(url), timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


def find_existing_service(data_dir):
    state = read_service_state(data_dir)
    if not state:
        return None
    if is_service_healthy(state["url"]):
        return state
    return None
