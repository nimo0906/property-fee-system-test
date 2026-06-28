# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder build spec for Windows desktop delivery."""

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
        ('新手交付说明.md', '.'),
        ('交付验收清单.md', '.'),
        ('清空本机试用数据.bat', '.'),
        ('Windows客户试用说明.md', '.'),
        ('check_windows_packaging_ready.bat', '.'),
        ('Windows打包操作步骤.md', '.'),
        ('Windows用户发送文案.md', '.'),
        ('真实数据导入前验收清单.md', '.'),
        ('真实数据试运行保护方案.md', '.'),
        ('update_manifest.json', '.'),
    ],
    hiddenimports=collect_submodules('openpyxl') + collect_submodules('xlrd'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PropertyFeeSystem',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='static/desktop-app-icon.ico',
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
    name='PropertyFeeSystem',
)
