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


APP_DIR_NAME = "PropertyFeeSystemData"
LEGACY_APP_DIR_NAME = "PropertyFeeSystem"
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


def get_legacy_app_data_dir(data_dir=None):
    if os.environ.get("PM_DATA_DIR"):
        return None
    if data_dir:
        current = Path(data_dir).expanduser()
        if current.name == APP_DIR_NAME:
            return current.parent / LEGACY_APP_DIR_NAME
        return None
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / LEGACY_APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / LEGACY_APP_DIR_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / LEGACY_APP_DIR_NAME


def copy_legacy_runtime_data(data_dir, db_path, backup_dir, log_dir):
    legacy_dir = get_legacy_app_data_dir(data_dir)
    if not legacy_dir or not legacy_dir.exists():
        return []
    copied = []
    legacy_db = legacy_dir / "property.db"
    if legacy_db.exists() and not db_path.exists():
        shutil.copy2(legacy_db, db_path)
        copied.append(f"database: {legacy_db} -> {db_path}")
    legacy_backups = legacy_dir / "backups"
    if legacy_backups.exists():
        for item in legacy_backups.iterdir():
            if item.is_file():
                target = backup_dir / item.name
                if not target.exists():
                    shutil.copy2(item, target)
                    copied.append(f"backup: {item} -> {target}")
    if copied:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "legacy_migration.log"
        log_path.write_text(
            "Copied legacy runtime data without deleting the original files.\n"
            + "\n".join(copied)
            + "\n",
            encoding="utf-8",
        )
    return copied


def prepare_runtime(data_dir=None):
    data_dir = Path(data_dir) if data_dir else get_app_data_dir()
    database_dir = data_dir / "database"
    backup_dir = data_dir / "backups"
    import_dir = data_dir / "imports"
    export_dir = data_dir / "exports"
    update_dir = data_dir / "updates"
    log_dir = data_dir / "logs"
    db_path = database_dir / "property.db"
    data_dir.mkdir(parents=True, exist_ok=True)
    for folder in (database_dir, backup_dir, import_dir, export_dir, update_dir, log_dir):
        folder.mkdir(parents=True, exist_ok=True)

    os.environ["PM_RESOURCE_DIR"] = str(get_resource_dir())
    copy_legacy_runtime_data(data_dir, db_path, backup_dir, log_dir)
    bundled_db = get_resource_dir() / "property.db"
    if not db_path.exists() and bundled_db.exists():
        shutil.copy2(bundled_db, db_path)

    os.environ["PM_DB_PATH"] = str(db_path)
    os.environ["PM_BACKUP_DIR"] = str(backup_dir)
    os.environ["PM_IMPORT_CACHE_DIR"] = str(import_dir)
    os.environ["PM_EXPORT_DIR"] = str(export_dir)
    os.environ["PM_UPDATE_DIR"] = str(update_dir)
    os.environ["PM_LOG_DIR"] = str(log_dir)
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
        "import_dir": str(data_dir / "imports"),
        "export_dir": str(data_dir / "exports"),
        "update_dir": str(data_dir / "updates"),
        "log_dir": str(data_dir / "logs"),
        "db_exists": db_path.exists(),
        "backup_dir_exists": backup_dir.exists(),
        "missing_dependencies": missing,
        "startup_log": str(data_dir / "logs" / "startup_error.log"),
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
        f"Import cache: {status.get('import_dir', '')}",
        f"Export directory: {status.get('export_dir', '')}",
        f"Update directory: {status.get('update_dir', '')}",
        f"Log directory: {status.get('log_dir', '')}",
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
    log_dir = Path(status.get("log_dir") or data_dir / "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "runtime_status.log"
    log_path.write_text(format_runtime_status(status), encoding="utf-8")
    return log_path


def build_window_model(url, data_dir, db_path, backup_dir):
    log_dir = Path(data_dir) / "logs"
    startup_log = log_dir / "startup_error.log"
    runtime_log = log_dir / "runtime_status.log"
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
            {"label": "检查更新", "kind": "open_update"},
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
        base = base / "logs"
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
