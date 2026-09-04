# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Multi-Executable Spec for IDM (Windows / Linux / macOS)
Packages:
- idm-gui (Windowed GUI)
- idm (CLI command)
- idm-daemon (Background service)
- idm-native-host (Browser Native Messaging Host)
"""

import os
import sys

block_cipher = None
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

datas = [
    (os.path.join(REPO_ROOT, "extension", "icons"), os.path.join("extension", "icons")),
    (os.path.join(REPO_ROOT, "scripts"), "scripts"),
]

bin_dir = os.path.join(REPO_ROOT, "bin")
if os.path.exists(bin_dir) and os.listdir(bin_dir):
    datas.append((bin_dir, "bin"))

icon_path = os.path.join(REPO_ROOT, "extension", "icons", "icon.ico")
if not os.path.exists(icon_path):
    icon_path = os.path.join(REPO_ROOT, "extension", "icons", "icon128.png")
if not os.path.exists(icon_path):
    icon_path = None

hidden_imports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "sqlite3",
    "urllib.parse",
    "urllib.request",
    "idm_core",
    "idm_ipc",
    "idm_gui",
    "idm_cli",
    "idm_native_host",
]

# 1. Main GUI App
a_gui = Analysis(
    [os.path.join(REPO_ROOT, "idm_gui", "app.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz_gui = PYZ(a_gui.pure, a_gui.zipped_data, cipher=block_cipher)
exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    [],
    exclude_binaries=True,
    name="idm-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed application
    icon=icon_path,
)
exe_pv_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    [],
    exclude_binaries=True,
    name="pv-idm-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_path,
)

# 2. CLI Tool
a_cli = Analysis(
    [os.path.join(REPO_ROOT, "idm_cli", "cli.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz_cli = PYZ(a_cli.pure, a_cli.zipped_data, cipher=block_cipher)
exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name="idm",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Console application
    icon=icon_path,
)
exe_pv_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name="pv-idm",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=icon_path,
)

# 3. Native Messaging Host
a_host = Analysis(
    [os.path.join(REPO_ROOT, "idm_native_host", "host.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz_host = PYZ(a_host.pure, a_host.zipped_data, cipher=block_cipher)
exe_host = EXE(
    pyz_host,
    a_host.scripts,
    [],
    exclude_binaries=True,
    name="idm-native-host",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # stdio native messaging host
    icon=icon_path,
)
exe_pv_host = EXE(
    pyz_host,
    a_host.scripts,
    [],
    exclude_binaries=True,
    name="pv-idm-native-host",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=icon_path,
)

# 4. Background Daemon
a_daemon = Analysis(
    [os.path.join(REPO_ROOT, "idm_ipc", "daemon.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz_daemon = PYZ(a_daemon.pure, a_daemon.zipped_data, cipher=block_cipher)
exe_daemon = EXE(
    pyz_daemon,
    a_daemon.scripts,
    [],
    exclude_binaries=True,
    name="idm-daemon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=icon_path,
)
exe_pv_daemon = EXE(
    pyz_daemon,
    a_daemon.scripts,
    [],
    exclude_binaries=True,
    name="pv-idm-daemon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=icon_path,
)

# Collective distribution bundle
coll = COLLECT(
    exe_pv_gui,
    exe_gui,
    a_gui.binaries,
    a_gui.zipfiles,
    a_gui.datas,
    exe_pv_cli,
    exe_cli,
    a_cli.binaries,
    a_cli.zipfiles,
    a_cli.datas,
    exe_pv_host,
    exe_host,
    a_host.binaries,
    a_host.zipfiles,
    a_host.datas,
    exe_pv_daemon,
    exe_daemon,
    a_daemon.binaries,
    a_daemon.zipfiles,
    a_daemon.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="pv-idm",
)
