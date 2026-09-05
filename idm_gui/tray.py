"""
System Tray Integration for IDM Linux
"""

import os
import sys
from typing import List, Optional
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


def get_icon_search_paths() -> List[str]:
    """Return list of candidate paths where icons might reside."""
    paths: List[str] = []
    # 1. Look in packaged icons directory inside idm_gui
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    paths.append(os.path.join(pkg_dir, "icons"))

    # 2. Look in repo layout relative to __file__
    paths.append(os.path.join(pkg_dir, "..", "extension", "icons"))
    paths.append(os.path.join(pkg_dir, "..", "_internal", "extension", "icons"))

    # 3. PyInstaller MEIPASS (frozen application)
    if hasattr(sys, "_MEIPASS"):
        paths.append(os.path.join(sys._MEIPASS, "extension", "icons"))
        paths.append(os.path.join(sys._MEIPASS, "idm_gui", "icons"))

    # 4. User opt directory (standalone bundle fallback)
    paths.append(os.path.expanduser("~/.local/opt/pv-idm/_internal/extension/icons"))
    return paths


def find_icon_file(filename: str) -> Optional[str]:
    """Find icon by filename across candidate locations and XDG icon directories."""
    for base in get_icon_search_paths():
        candidate = os.path.join(base, filename)
        if os.path.isfile(candidate):
            return candidate

    # Check XDG hicolor icon directories on Linux (e.g. icon32.png -> 32x32/apps/pv-idm.png)
    if filename.startswith("icon") and filename.endswith(".png"):
        size_part = filename[4:-4]
        if size_part.isdigit():
            sz = f"{size_part}x{size_part}"
            for xdg_base in [
                os.path.expanduser("~/.local/share/icons/hicolor"),
                "/usr/local/share/icons/hicolor",
                "/usr/share/icons/hicolor",
            ]:
                candidate = os.path.join(xdg_base, sz, "apps", "pv-idm.png")
                if os.path.isfile(candidate):
                    return candidate
                candidate_old = os.path.join(xdg_base, sz, "apps", "idm-linux.png")
                if os.path.isfile(candidate_old):
                    return candidate_old
    return None


def create_app_icon() -> QIcon:
    """Create multi-resolution application icon."""
    # 1. Try system theme icon first on Linux
    theme_icon = QIcon.fromTheme("pv-idm")
    if theme_icon.isNull():
        theme_icon = QIcon.fromTheme("idm-linux")
    if not theme_icon.isNull():
        return theme_icon

    # 2. Build multi-resolution icon from search candidates
    icon = QIcon()
    for sz in [16, 32, 48, 128, 256, 512]:
        p = find_icon_file(f"icon{sz}.png")
        if p and os.path.isfile(p):
            icon.addFile(p)

    if not icon.isNull():
        return icon

    return QIcon(create_tray_icon_pixmap())


def create_tray_icon_pixmap() -> QPixmap:
    """Draw clean IDM emblem tray icon."""
    # 1. Try system theme icon first
    theme_icon = QIcon.fromTheme("pv-idm")
    if theme_icon.isNull():
        theme_icon = QIcon.fromTheme("idm-linux")
    if not theme_icon.isNull():
        pm = theme_icon.pixmap(32, 32)
        if not pm.isNull():
            return pm

    # 2. Search candidate files
    for sz in ["icon48.png", "icon32.png", "icon128.png", "icon16.png", "icon64.png", "icon256.png"]:
        icon_path = find_icon_file(sz)
        if icon_path and os.path.isfile(icon_path):
            return QPixmap(icon_path)

    # 3. Dynamic fallback (only if no icon could be resolved anywhere)
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))
    p = QPainter(pixmap)
    p.setBrush(QColor("#3182ce"))
    p.setPen(QColor("#63b3ed"))
    p.drawRoundedRect(2, 2, 28, 28, 6, 6)
    p.end()
    return pixmap


class IDMTrayIcon(QSystemTrayIcon):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window

        self.setIcon(QIcon(create_tray_icon_pixmap()))
        self.setToolTip("PV-IDM - Internet Download Manager")

        self._setup_menu()
        self.activated.connect(self._on_activated)

    def _setup_menu(self):
        menu = QMenu()

        show_act = menu.addAction("Show IDM")
        show_act.triggered.connect(self._toggle_visibility)

        add_act = menu.addAction("➕ Add URL...")
        add_act.triggered.connect(self.main_window.open_add_url_dialog)

        menu.addSeparator()

        stop_all_act = menu.addAction("⏹ Stop All Downloads")
        stop_all_act.triggered.connect(self.main_window.stop_all_downloads)

        start_q_act = menu.addAction("▶ Start Queue")
        start_q_act.triggered.connect(self.main_window.start_queue)

        menu.addSeparator()

        options_act = menu.addAction("⚙ Options...")
        options_act.triggered.connect(self.main_window.open_options_dialog)

        exit_act = menu.addAction("❌ Exit IDM")
        exit_act.triggered.connect(self.main_window.quit_application)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_visibility()

    def _toggle_visibility(self):
        if self.main_window.isVisible():
            self.main_window.hide()
        else:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

    def show_notification(self, title: str, message: str):
        from idm_core.platform import show_desktop_notification
        icon_path = find_icon_file("icon128.png") or find_icon_file("icon48.png")
        if not show_desktop_notification(title, message, icon_path=icon_path):
            self.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000
            )
