#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desktop runtime helpers for the property fee system."""

import importlib.util
import os
import shutil
import socket
import sys
import time
import traceback
from pathlib import Path


APP_DIR_NAME = "PropertyFeeSystem"
APP_TITLE = "物业管理收费系统"


def get_resource_dir():
    """Return the source/bundled resource directory for templates and static files."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    return Path(__file__).resolve().parent


def get_app_data_dir():
    override = os.environ.get("PM_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME


def prepare_runtime(data_dir=None):
    data_dir = Path(data_dir) if data_dir else get_app_data_dir()
    backup_dir = data_dir / "backups"
    db_path = data_dir / "property.db"
    data_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    os.environ["PM_RESOURCE_DIR"] = str(get_resource_dir())
    bundled_db = get_resource_dir() / "property.db"
    if not db_path.exists() and bundled_db.exists():
        shutil.copy2(bundled_db, db_path)

    os.environ["PM_DB_PATH"] = str(db_path)
    os.environ["PM_BACKUP_DIR"] = str(backup_dir)
    os.environ.setdefault("PM_HOST", "127.0.0.1")
    return data_dir, db_path, backup_dir


def get_runtime_status(data_dir=None, dependencies=None):
    data_dir, db_path, backup_dir = prepare_runtime(data_dir)
    dependencies = dependencies or ["openpyxl", "xlrd"]
    missing = [name for name in dependencies if importlib.util.find_spec(name) is None]
    return {
        "app_title": APP_TITLE,
        "python_version": sys.version.split()[0],
        "executable": sys.executable,
        "data_dir": str(data_dir),
        "db_path": str(db_path),
        "backup_dir": str(backup_dir),
        "db_exists": db_path.exists(),
        "backup_dir_exists": backup_dir.exists(),
        "missing_dependencies": missing,
        "startup_log": str(data_dir / "startup_error.log"),
    }


def format_runtime_status(status):
    missing = status.get("missing_dependencies") or []
    lines = [
        status.get("app_title", APP_TITLE),
        f"Python: {status.get('python_version', '')}",
        f"Executable: {status.get('executable', '')}",
        f"Data directory: {status.get('data_dir', '')}",
        f"Database: {status.get('db_path', '')}",
        f"Backup directory: {status.get('backup_dir', '')}",
        f"Database exists: {'yes' if status.get('db_exists') else 'no'}",
        f"Backup directory exists: {'yes' if status.get('backup_dir_exists') else 'no'}",
    ]
    if missing:
        lines.append(f"Missing dependencies: {', '.join(missing)}")
        lines.append("Run install_windows_dependencies.bat, then start the system again.")
    else:
        lines.append("Missing dependencies: none")
    if status.get("startup_log"):
        lines.append(f"Startup error log: {status['startup_log']}")
    return "\n".join(lines)


def write_runtime_status_log(status):
    """Write current runtime diagnostics for support and return the log path."""
    data_dir = Path(status["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "runtime_status.log"
    log_path.write_text(format_runtime_status(status), encoding="utf-8")
    return log_path


def build_window_model(url, data_dir, db_path, backup_dir):
    startup_log = Path(data_dir) / "startup_error.log"
    runtime_log = Path(data_dir) / "runtime_status.log"
    return {
        "title": APP_TITLE,
        "url": url,
        "data_dir": str(data_dir),
        "db_path": str(db_path),
        "backup_dir": str(backup_dir),
        "startup_log": str(startup_log),
        "runtime_log": str(runtime_log),
        "service_status": f"当前访问地址: {url}",
        "hint": "数据保存在本机，关闭窗口会停止本地服务。启动失败时请查看诊断信息或错误日志。",
        "actions": [
            {"label": "打开系统", "kind": "open_url"},
            {"label": "重新启动服务", "kind": "restart_service"},
            {"label": "打开数据目录", "kind": "open_folder"},
            {"label": "查看诊断信息", "kind": "diagnose"},
            {"label": "打开错误日志", "kind": "open_startup_log"},
            {"label": "退出", "kind": "exit"},
        ],
    }


def choose_desktop_port(start=5001):
    """Prefer the documented local port, then fall back to the next free port."""
    return find_free_port(start, attempts=100)


def find_free_port(start=5000, attempts=100):
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    end = start + attempts - 1
    raise RuntimeError(f"No free local port found in range {start}-{end}")


def write_startup_error(exc, data_dir=None):
    """Write a readable startup error log and return its path."""
    try:
        base = Path(data_dir) if data_dir else get_app_data_dir()
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        base = Path.cwd()
    log_path = base / "startup_error.log"
    text = [
        f"{APP_TITLE} startup failed",
        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Python: {sys.version}",
        f"Executable: {sys.executable}",
        f"Working directory: {Path.cwd()}",
        "",
        "Traceback:",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    ]
    log_path.write_text("\n".join(text), encoding="utf-8")
    return log_path


def open_path(path):
    path = Path(path)
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}"')
