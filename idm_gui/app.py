"""
PyQt6 Application Runner for IDM Linux
Handles single-instance IPC handoff, command-line arguments, and main loop.
"""

import argparse
import os
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication
from idm_core.config import Config
from idm_core.engine import DownloadEngine
from idm_gui.main_window import MainWindow
from idm_gui.styles import IDM_DARK_THEME
from idm_gui.tray import IDMTrayIcon, create_tray_icon_pixmap
from idm_ipc.socket_client import IPCClient
from idm_ipc.socket_server import IPCServer


def main():
    parser = argparse.ArgumentParser(description="IDM Linux Desktop Application")
    parser.add_argument("--minimized", action="store_true", help="Start minimized in system tray")
    parser.add_argument("--url", help="Download URL to add immediately")
    parser.add_argument("--config-dir", help="Custom config directory")
    args = parser.parse_args()

    config = Config()
    if args.config_dir:
        config = Config(config_dir=args.config_dir)

    # 1. Single-instance check via IPC
    client = IPCClient(config.socket_path)
    if client.is_server_running():
        if args.url:
            print(f"[IDM] Forwarding URL to running IDM instance: {args.url}")
            client.send_request({
                "action": "add_download",
                "url": args.url,
                "start_immediately": True
            })
        else:
            print("[IDM] IDM is already running. Raising existing window.")
            client.send_request({"action": "show_gui"})
        sys.exit(0)

    # 2. Launch Main Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("IDM Linux")
    app.setOrganizationName("IDM Linux Team")
    app.setWindowIcon(QIcon(create_tray_icon_pixmap()))
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

    if args.url:
        window.open_add_url_dialog(default_url=args.url)

    exit_code = app.exec()

    # Clean shutdown
    server.stop()
    engine.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
