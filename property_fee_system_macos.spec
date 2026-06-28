# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller macOS app bundle spec for local desktop delivery."""

from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path


def clean_tree(src, dest):
    result = []
    for path in Path(src).rglob('*'):
        if not path.is_file():
            continue
        if '__pycache__' in path.parts or path.suffix in {'.pyc', '.pyo'} or path.name == '.DS_Store':
            continue
        target = Path(dest) / path.relative_to(src).parent
        result.append((str(path), str(target)))
    return result

block_cipher = None

a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=clean_tree('server', 'server') + clean_tree('templates', 'templates') + clean_tree('static', 'static') + [
        ('requirements.txt', '.'),
        ('使用说明.md', '.'),
        ('用户快速开始.md', '.'),
        ('update_manifest.json', '.'),
    ],
    hiddenimports=collect_submodules('openpyxl') + collect_submodules('xlrd'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='物业管理收费系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='物业管理收费系统',
)
app = BUNDLE(
    coll,
    name='物业管理收费系统.app',
    icon='static/desktop-app-icon.icns',
    bundle_identifier='local.propertyfeesystem.desktop',
    info_plist={
        'CFBundleName': '物业管理收费系统',
        'CFBundleDisplayName': '物业管理收费系统',
        'CFBundleShortVersionString': '2.0.4',
        'CFBundleVersion': '2.0.4',
        'NSHighResolutionCapable': 'True',
    },
)
