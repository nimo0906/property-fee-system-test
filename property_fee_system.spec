# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder build spec for Windows desktop delivery."""

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('server', 'server'),
        ('templates', 'templates'),
        ('static', 'static'),
        ('requirements.txt', '.'),
        ('使用说明.md', '.'),
        ('用户快速开始.md', '.'),
        ('交付验收清单.md', '.'),
        ('清空本机试用数据.bat', '.'),
        ('Windows客户试用说明.md', '.'),
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
