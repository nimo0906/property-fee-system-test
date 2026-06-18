#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local desktop release asset checker for macOS and Windows packaging."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

TEXT_CHECKS = [
    ('macOS app display name', ROOT / 'property_fee_system_macos.spec', '物业收费管理系统.app'),
    ('Windows exe name', ROOT / 'property_fee_system.spec', 'PropertyBillingSystem'),
    ('Windows package name', ROOT / 'package_windows_release.bat', '物业收费管理系统-v2.0-windows'),
    ('license example', ROOT / 'license.example.json', 'customer_name'),
    ('commercial delivery checklist', ROOT / 'docs' / 'commercial-delivery-checklist.md', 'PropertyBillingSystem.exe'),
]

CHECKS = [
    ('desktop app entry', ROOT / 'desktop_app.py'),
    ('desktop runtime', ROOT / 'desktop_runtime.py'),
    ('macOS build script', ROOT / 'build_macos_app.command'),
    ('macOS PyInstaller spec', ROOT / 'property_fee_system_macos.spec'),
    ('Windows dependency installer', ROOT / 'install_windows_dependencies.bat'),
    ('Windows build script', ROOT / 'build_windows_exe.bat'),
    ('Windows diagnosis script', ROOT / 'diagnose_windows.bat'),
    ('Windows PyInstaller spec', ROOT / 'property_fee_system.spec'),
    ('macOS desktop icon', ROOT / 'static' / 'desktop-app-icon.icns'),
    ('Windows desktop icon', ROOT / 'static' / 'desktop-app-icon.ico'),
    ('release checklist', ROOT / 'docs' / 'desktop-release-checklist.md'),
    ('hidden module policy', ROOT / 'docs' / 'hidden-module-policy.md'),
    ('source tree hygiene guard', ROOT / 'scripts' / 'source_tree_check.py'),
]


def main():
    missing = []
    for label, path in CHECKS:
        if path.exists():
            print(f'PASS {label}: {path.relative_to(ROOT)}')
        else:
            print(f'FAIL {label}: {path.relative_to(ROOT)}')
            missing.append(label)
    for label, path, expected in TEXT_CHECKS:
        if not path.exists():
            print(f'FAIL {label}: {path.relative_to(ROOT)}')
            missing.append(label)
            continue
        text = path.read_text(encoding='utf-8')
        if expected in text:
            print(f'PASS {label}: {path.relative_to(ROOT)}')
        else:
            print(f'FAIL {label}: missing {expected}')
            missing.append(label)
    if missing:
        print('Missing assets: ' + ', '.join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
