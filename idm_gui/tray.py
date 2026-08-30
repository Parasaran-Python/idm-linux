"""
System Tray Integration for IDM Linux
"""

import os
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


def create_app_icon() -> QIcon:
    """Create multi-resolution application icon."""
    icon = QIcon()
    icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extension", "icons")
    for sz in [16, 32, 48, 128, 256, 512]:
        p = os.path.join(icons_dir, f"icon{sz}.png")
        if os.path.exists(p):
            icon.addFile(p)
    return icon


def create_tray_icon_pixmap() -> QPixmap:
    """Draw clean IDM emblem tray icon."""
    icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extension", "icons")
    for sz in ["icon48.png", "icon32.png", "icon128.png", "icon16.png"]:
        icon_path = os.path.join(icons_dir, sz)
        if os.path.exists(icon_path):
            return QPixmap(icon_path)
    
    # Dynamic fallback
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
        self.setToolTip("IDM Linux - Internet Download Manager")

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
        self.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )
