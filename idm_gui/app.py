"""
PyQt6 Application Runner for IDM Linux
Handles single-instance IPC handoff, command-line arguments, and main loop.
"""

import argparse
import os
import sys
import traceback
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication
from idm_core.config import Config
from idm_core.engine import DownloadEngine
from idm_core.platform import (
    is_linux,
    setup_windows_app_id,
    is_native_messaging_host_registered,
    register_native_messaging_host,
    resolve_native_host_binary,
)
from idm_gui.main_window import MainWindow
from idm_gui.styles import IDM_DARK_THEME
from idm_gui.tray import IDMTrayIcon, create_tray_icon_pixmap, create_app_icon
from idm_ipc.socket_client import IPCClient
from idm_ipc.socket_server import IPCServer


def _handle_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    print("[IDM Unhandled Exception]:", file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_tb)


sys.excepthook = _handle_exception
if hasattr(sys, "unraisablehook"):
    sys.unraisablehook = lambda u: print(f"[IDM Unraisable Warning]: {u.exc_value}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="IDM Linux Desktop Application")
    parser.add_argument("urls", nargs="*", default=[], help="Optional download URLs to add")
    parser.add_argument("--minimized", action="store_true", help="Start minimized in system tray")
    parser.add_argument("--url", help="Download URL to add immediately")
    parser.add_argument("--config-dir", help="Custom config directory")
    args = parser.parse_args()

    # Cleanly extract target URL, ignoring empty desktop launcher %U expansions
    target_url = None
    if args.url and args.url.strip().startswith(("http://", "https://", "ftp://", "idm://")):
        target_url = args.url.strip()
    elif args.urls:
        for u in args.urls:
            candidate = (u or "").strip()
            if candidate.startswith(("http://", "https://", "ftp://", "idm://")):
                target_url = candidate
                break

    config = Config()
    if args.config_dir:
        config = Config(config_dir=args.config_dir)

    # 1. Single-instance check via IPC
    client = IPCClient(config.socket_path)
    if client.is_server_running():
        if target_url:
            print(f"[IDM] Forwarding URL to running IDM instance: {target_url}")
            client.send_request({
                "action": "add_download",
                "url": target_url,
                "start_immediately": True
            })
            client.send_request({"action": "show_gui"})
        else:
            print("[IDM] IDM is already running. Raising existing window.")
            client.send_request({"action": "show_gui"})
        sys.exit(0)

    # Configure Windows App ID for taskbar grouping & notifications
    setup_windows_app_id()

    # Auto-register native messaging host for browser integration on Windows if missing or moved
    if sys.platform == "win32":
        try:
            current_host = resolve_native_host_binary()
            if not is_native_messaging_host_registered(expected_binary=current_host):
                register_native_messaging_host(binary_path=current_host)
        except Exception as e:
            print(f"[IDM] Note: Auto-registering native messaging host failed: {e}", file=sys.stderr)

    # Enable native window decorations & titlebar controls on Linux
    if is_linux():
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb;wayland")

    # 2. Launch Main Qt Application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setApplicationName("idm-linux")
    app.setApplicationDisplayName("IDM Linux")
    app.setOrganizationName("IDM Linux Team")
    app.setDesktopFileName("idm-linux.desktop")
    app.setWindowIcon(create_app_icon())
    app.setStyleSheet(IDM_DARK_THEME)

    # Start core engine and IPC server
    engine = DownloadEngine(config)
    server = IPCServer(engine, config.socket_path)
    server.start()

    window = MainWindow(engine=engine, config=config)
    tray = IDMTrayIcon(window)
    tray.show()

    if not args.minimized:
        window.show()

    if target_url:
        window.open_add_url_dialog(default_url=target_url)

    exit_code = app.exec()

    # Clean shutdown
    server.stop()
    engine.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
