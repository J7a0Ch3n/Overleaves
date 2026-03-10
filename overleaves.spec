# -*- mode: python ; coding: utf-8 -*-
"""
Overleaves PyInstaller 打包配置
使用方式：pyinstaller overleaves.spec
"""
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        # flet_desktop/app 是 Flet 0.82 桌面运行时（Flutter 渲染引擎 + DLL）
        # 旧版路径 flet/app 在 Flet 0.82 中已不存在，正确路径在 flet_desktop 包下
        (
            str(Path(sys.executable).parent / 'Lib/site-packages/flet_desktop/app'),
            'flet_desktop/app'
        ),
    ],
    hiddenimports=[
        'flet',
        'flet_desktop',
        'fitz',
        'requests',
        'config.settings_manager',
        'storage.local_storage',
        'overleaf.client',
        'overleaf.exceptions',
        'gui.app',
        'gui.settings',
        'gui.panels.file_tree',
        'gui.panels.tex_viewer',
        'gui.panels.pdf_viewer',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='overleaves',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # --windowed: 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 可替换为 .ico 文件路径
)
