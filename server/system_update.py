#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Semi-automatic desktop update checks and package preparation."""

import hashlib
import json
import os
import shlex
import shutil
import stat
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from desktop_runtime import get_app_data_dir, get_resource_dir
from server.app_version import APP_VERSION, DEFAULT_UPDATE_MANIFEST_URL


class UpdateError(Exception):
    """Safe update error that can be shown in the admin UI."""


def _version_tuple(value):
    parts = []
    for item in str(value or '').replace('-', '.').split('.'):
        digits = ''.join(ch for ch in item if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts or [0])


def compare_versions(left, right):
    a = list(_version_tuple(left))
    b = list(_version_tuple(right))
    size = max(len(a), len(b))
    a.extend([0] * (size - len(a)))
    b.extend([0] * (size - len(b)))
    return (a > b) - (a < b)


def current_platform_key():
    if sys.platform == 'darwin':
        return 'mac'
    if sys.platform.startswith('win'):
        return 'windows'
    return 'linux'


def _safe_name(value):
    return ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in str(value or 'update'))


class SystemUpdateService:
    def __init__(self, current_version=None, platform_key=None, manifest_url=None, data_dir=None, app_root=None, process_id=None):
        self.current_version = current_version or APP_VERSION
        self.platform_key = platform_key or current_platform_key()
        self.manifest_url = manifest_url or DEFAULT_UPDATE_MANIFEST_URL
        self.data_dir = Path(data_dir) if data_dir else get_app_data_dir()
        self.app_root = Path(app_root) if app_root else self.detect_app_root()
        self.process_id = process_id or os.getpid()

    def detect_app_root(self):
        exe = Path(sys.executable).resolve()
        if self.platform_key == 'mac':
            for parent in [exe] + list(exe.parents):
                if parent.suffix == '.app':
                    return parent
        if self.platform_key == 'windows':
            return exe.parent
        return get_resource_dir()

    def is_packaged_runtime(self):
        if getattr(sys, 'frozen', False):
            return True
        if self.platform_key == 'mac' and self.app_root.suffix == '.app':
            return True
        if self.platform_key == 'windows' and self.app_root.joinpath('PropertyFeeSystem.exe').exists():
            return True
        return os.environ.get('PM_ALLOW_SOURCE_UPDATE') == '1'

    def fetch_manifest(self):
        try:
            with urllib.request.urlopen(self.manifest_url, timeout=10) as resp:
                raw = resp.read().decode('utf-8')
            return json.loads(raw)
        except Exception as exc:
            raise UpdateError('无法读取更新清单: ' + str(exc))

    def check_manifest(self, manifest):
        latest = str(manifest.get('version') or '').strip()
        if not latest:
            raise UpdateError('更新清单缺少 version')
        asset = self._asset_for_platform(manifest)
        return {
            'current_version': self.current_version,
            'latest_version': latest,
            'update_available': compare_versions(latest, self.current_version) > 0,
            'notes': manifest.get('notes') or '',
            'platform': self.platform_key,
            'asset_url': asset.get('url') or '',
            'asset_sha256': asset.get('sha256') or '',
            'manifest_url': self.manifest_url,
        }

    def _asset_for_platform(self, manifest):
        assets = manifest.get('assets') or {}
        asset = assets.get(self.platform_key) or {}
        legacy_url = manifest.get('mac_url' if self.platform_key == 'mac' else 'windows_url')
        if legacy_url and not asset.get('url'):
            asset = {'url': legacy_url, 'sha256': (manifest.get('sha256') or {}).get(self.platform_key, '')}
        return asset

    def check_for_update(self):
        return self.check_manifest(self.fetch_manifest())

    def prepare_from_manifest(self, manifest=None):
        manifest = manifest or self.fetch_manifest()
        info = self.check_manifest(manifest)
        if not info['update_available']:
            raise UpdateError('当前已经是最新版本')
        if not info['asset_url']:
            raise UpdateError('更新清单没有提供当前平台的下载地址')
        if not self.is_packaged_runtime():
            raise UpdateError('当前是源码运行模式，不能自动替换程序；请在打包后的桌面版中执行更新')
        package = self.download_package(info['asset_url'], info['latest_version'])
        prepared = self.prepare_package(package, info['latest_version'], info.get('asset_sha256') or '')
        prepared.update(info)
        return prepared

    def download_package(self, url, version):
        target_dir = self.data_dir / 'updates' / 'downloads'
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = '.zip' if not str(url).split('?')[0].lower().endswith('.zip') else ''
        target = target_dir / f'{self.platform_key}-{_safe_name(version)}{suffix or ".zip"}'
        try:
            with urllib.request.urlopen(url, timeout=60) as resp, target.open('wb') as out:
                shutil.copyfileobj(resp, out)
            return target
        except Exception as exc:
            raise UpdateError('下载更新包失败: ' + str(exc))

    def prepare_package(self, package_path, version, expected_sha256=''):
        package_path = Path(package_path)
        if expected_sha256:
            actual = hashlib.sha256(package_path.read_bytes()).hexdigest()
            if actual.lower() != expected_sha256.lower():
                raise UpdateError('更新包校验失败')
        base = self.data_dir / 'updates'
        stamp = time.strftime('%Y%m%d_%H%M%S')
        extract_dir = base / 'extracted' / f'{_safe_name(version)}_{self.platform_key}_{stamp}'
        helper_dir = base / 'helpers'
        extract_dir.mkdir(parents=True, exist_ok=True)
        helper_dir.mkdir(parents=True, exist_ok=True)
        self._extract_safe(package_path, extract_dir)
        payload = self._find_payload(extract_dir)
        helper = self._write_helper(helper_dir, payload, version, stamp)
        return {
            'version': version,
            'package_path': str(package_path),
            'extract_dir': str(extract_dir),
            'payload_path': str(payload),
            'helper_path': str(helper),
            'app_root': str(self.app_root),
            'backup_dir': str(base / 'previous_versions'),
        }

    def _extract_safe(self, package_path, extract_dir):
        with zipfile.ZipFile(package_path) as zf:
            for info in zf.infolist():
                dest = (extract_dir / info.filename).resolve()
                root = extract_dir.resolve()
                if dest != root and root not in dest.parents:
                    raise UpdateError('更新包包含不安全路径')
            zf.extractall(extract_dir)

    def _find_payload(self, extract_dir):
        if self.platform_key == 'mac':
            apps = [p for p in extract_dir.rglob('*.app') if p.is_dir()]
            if apps:
                return apps[0]
            raise UpdateError('更新包中没有找到 macOS .app')
        if self.platform_key == 'windows':
            exes = [p for p in extract_dir.rglob('PropertyFeeSystem.exe') if p.is_file()]
            if exes:
                return exes[0].parent
            raise UpdateError('更新包中没有找到 PropertyFeeSystem.exe')
        raise UpdateError('暂不支持当前平台自动更新')

    def _write_helper(self, helper_dir, payload, version, stamp):
        if self.platform_key == 'windows':
            path = helper_dir / f'run_update_{_safe_name(version)}.bat'
            text = self._windows_helper(payload, stamp)
        else:
            path = helper_dir / f'run_update_{_safe_name(version)}.command'
            text = self._mac_helper(payload, stamp)
        path.write_text(text, encoding='utf-8')
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return path

    def _mac_helper(self, payload, stamp):
        app_root = shlex.quote(str(self.app_root))
        payload_q = shlex.quote(str(payload))
        backup = shlex.quote(str(self.data_dir / 'updates' / 'previous_versions' / f'{self.app_root.name}.{stamp}.backup'))
        return f'''#!/bin/zsh
set -e
echo "物业管理收费系统更新助手"
echo "请先退出当前系统窗口。"
while kill -0 {int(self.process_id)} 2>/dev/null; do
  sleep 1
done
mkdir -p {shlex.quote(str(self.data_dir / 'updates' / 'previous_versions'))}
if [ -d {app_root} ]; then
  rm -rf {backup}
  mv {app_root} {backup}
fi
ditto {payload_q} {app_root}
open {app_root} || true
echo "更新完成。旧版本备份在: {backup}"
read "?按回车关闭窗口..."
'''

    def _windows_helper(self, payload, stamp):
        app_root = str(self.app_root)
        backup = str(self.data_dir / 'updates' / 'previous_versions' / f'{self.app_root.name}.{stamp}.backup')
        exe = str(Path(app_root) / 'PropertyFeeSystem.exe')
        return f'''@echo off
chcp 65001 >nul
echo 物业管理收费系统更新助手
echo 请先退出当前系统窗口。
:wait_loop
tasklist /FI "PID eq {int(self.process_id)}" | find "{int(self.process_id)}" >nul
if not errorlevel 1 (
  timeout /t 1 >nul
  goto wait_loop
)
if not exist "{str(Path(backup).parent)}" mkdir "{str(Path(backup).parent)}"
if exist "{backup}" rmdir /S /Q "{backup}"
if exist "{app_root}" move "{app_root}" "{backup}" >nul
xcopy "{str(payload)}" "{app_root}\\" /E /I /H /Y >nul
start "" "{exe}"
echo 更新完成。旧版本备份在: {backup}
pause
'''
