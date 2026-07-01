#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create an ASCII-only Windows source package for building on Windows."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / 'release' / 'windows-source'
PACKAGE_PREFIX = 'PropertyFeeSystem-windows-source'

ROOT_FILES = [
    'desktop_app.py',
    'desktop_runtime.py',
    'desktop_service_guard.py',
    'server.py',
    'requirements.txt',
    'property_fee_system.spec',
    'PACK_WINDOWS_RELEASE.bat',
    'CHECK_WINDOWS_ENV.bat',
    'package_windows_release.bat',
    'check_windows_packaging_ready.bat',
    'USER_GUIDE_WINDOWS.txt',
    'build_windows_exe.bat',
    'install_windows_dependencies.bat',
    'diagnose_windows.bat',
    'start_windows.bat',
    'start_windows_server.bat',
    'install_windows_background_task.bat',
    'status_windows_background_task.bat',
    'uninstall_windows_background_task.bat',
    'RESET_TRIAL_DATA.bat',
    'update_manifest.json',
]

TREE_DIRS = [
    'server',
    'templates',
    'static',
]

SKIP_DIR_NAMES = {
    '.git', '.github', '.claude', '.claudian', '.obsidian', '.pytest_cache',
    '.smart-env', '__pycache__', 'build', 'dist', 'release', 'logs', 'backups',
}
SKIP_SUFFIXES = {'.pyc', '.pyo', '.log'}
SKIP_NAMES = {'.DS_Store', '.env', 'property.db', 'property.db-wal', 'property.db-shm'}


def is_ascii_path(path: Path | str) -> bool:
    return all(ord(ch) < 128 for ch in Path(path).as_posix())


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if not is_ascii_path(rel):
        return True
    if any(part in SKIP_DIR_NAMES for part in rel.parts):
        return True
    if path.name in SKIP_NAMES:
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    return False


def copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src.relative_to(ROOT))
    if should_skip(src):
        raise ValueError(f'unsafe package input: {src.relative_to(ROOT)}')
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src_dir: Path, dst_dir: Path) -> None:
    for src in src_dir.rglob('*'):
        if not src.is_file() or should_skip(src):
            continue
        copy_file(src, dst_dir / src.relative_to(src_dir))


def validate_tree(package_dir: Path) -> list[str]:
    failures: list[str] = []
    required = ROOT_FILES + TREE_DIRS
    for rel in required:
        if not (package_dir / rel).exists():
            failures.append(f'missing {rel}')
    for path in package_dir.rglob('*'):
        rel = path.relative_to(package_dir)
        if not is_ascii_path(rel):
            failures.append(f'non-ascii path {rel}')
        if path.is_file():
            if path.name in SKIP_NAMES or path.suffix in SKIP_SUFFIXES:
                failures.append(f'forbidden file {rel}')
            if any(part in SKIP_DIR_NAMES for part in rel.parts):
                failures.append(f'forbidden dir member {rel}')
    return failures


def zip_dir(package_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_dir.rglob('*')):
            if path.is_file():
                zf.write(path, path.relative_to(package_dir.parent).as_posix())


def validate_zip(zip_path: Path) -> list[str]:
    failures: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    for name in names:
        if any(ord(ch) > 127 for ch in name):
            failures.append(f'zip non-ascii path {name}')
        parts = Path(name).parts
        if any(part in SKIP_DIR_NAMES for part in parts):
            failures.append(f'zip forbidden dir member {name}')
        leaf = parts[-1] if parts else name
        suffix = Path(leaf).suffix
        if leaf in SKIP_NAMES or suffix in SKIP_SUFFIXES:
            failures.append(f'zip forbidden file {name}')
    required_zip_entries = [
        'PACK_WINDOWS_RELEASE.bat',
        'CHECK_WINDOWS_ENV.bat',
        'USER_GUIDE_WINDOWS.txt',
        'desktop_app.py',
        'desktop_runtime.py',
        'desktop_service_guard.py',
        'server.py',
        'property_fee_system.spec',
        'server/__init__.py',
        'templates/base.html',
        'static/desktop-app-icon.ico',
    ]
    top = zip_path.stem
    for rel in required_zip_entries:
        if f'{top}/{rel}' not in names:
            failures.append(f'zip missing {rel}')
    return failures


def main() -> int:
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    package_name = f'{PACKAGE_PREFIX}-{stamp}'
    package_dir = RELEASE_ROOT / package_name
    zip_path = RELEASE_ROOT / f'{package_name}.zip'

    if package_dir.exists():
        shutil.rmtree(package_dir)
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)

    for rel in ROOT_FILES:
        copy_file(ROOT / rel, package_dir / rel)
    for rel in TREE_DIRS:
        copy_tree(ROOT / rel, package_dir / rel)

    failures = validate_tree(package_dir)
    if failures:
        for item in failures:
            print(f'FAIL {item}', file=sys.stderr)
        return 1

    if zip_path.exists():
        zip_path.unlink()
    zip_dir(package_dir, zip_path)
    shutil.rmtree(package_dir)

    failures = validate_zip(zip_path)
    if failures:
        for item in failures:
            print(f'FAIL {item}', file=sys.stderr)
        return 1

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    print(f'ZIP={zip_path}')
    print(f'ENTRY_COUNT={len(names)}')
    print('NON_ASCII_COUNT=0')
    print('FORBIDDEN_COUNT=0')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
