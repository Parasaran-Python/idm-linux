"""
Complete IDM Main Window Interface with Classic Toolbar, Categories & Table
"""

import os
import sys
from typing import Dict, List, Optional
from PyQt6.QtCore import QObject, QPoint, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from idm_core.config import Config
from idm_core.engine import DownloadEngine
from idm_gui.dialogs.batch_download_dialog import BatchDownloadDialog
from idm_gui.dialogs.delete_dialog import DeleteConfirmDialog
from idm_gui.dialogs.download_info_dialog import DownloadInfoDialog
from idm_gui.dialogs.download_progress_dialog import DownloadProgressDialog
from idm_gui.dialogs.options_dialog import OptionsDialog
from idm_gui.dialogs.queue_scheduler_dialog import QueueSchedulerDialog
from idm_gui.styles import IDM_DARK_THEME
from idm_gui.widgets.category_tree import CategoryTreeWidget
from idm_gui.widgets.download_table import DownloadTableWidget, format_bytes, format_speed


class EngineEventBridge(QObject):
    """Thread-safe event bridge using Qt queued connections to marshal engine events to GUI thread."""
    download_progress = pyqtSignal(dict)
    segment_update = pyqtSignal(dict)
    download_started = pyqtSignal(dict)
    download_paused = pyqtSignal(dict)
    download_completed = pyqtSignal(dict)
    download_error = pyqtSignal(dict)
    download_requested = pyqtSignal(dict)
    show_gui = pyqtSignal(dict)


class MainWindow(QMainWindow):
    def __init__(self, engine: Optional[DownloadEngine] = None, config: Optional[Config] = None, parent=None):
        super().__init__(parent)
        self.config = config or Config()
        self.engine = engine or DownloadEngine(self.config)

        self.setWindowTitle("PV-IDM - Internet Download Manager")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(1020, 640)
        self.setStyleSheet(IDM_DARK_THEME)

        self.current_category = "All Downloads"
        self.current_search = ""
        self.progress_dialogs: Dict[str, DownloadProgressDialog] = {}

        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_events()

        # Refresh timer (500ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_downloads)
        self.timer.start(500)

        self.refresh_downloads()

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Search Bar
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter downloads by name or URL...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        main_layout.addLayout(search_layout)

        # Splitter: Category sidebar on left, Download table on right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.category_tree = CategoryTreeWidget()
        self.category_tree.category_selected.connect(self._on_category_selected)
        self.category_tree.queue_selected.connect(self._on_queue_selected)
        splitter.addWidget(self.category_tree)

        self.table = DownloadTableWidget()
        self.table.download_double_clicked.connect(self._on_download_double_clicked)
        self.table.action_requested.connect(self._on_table_action)
        splitter.addWidget(self.table)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([200, 800])

        main_layout.addWidget(splitter)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_count_label = QLabel("Total: 0")
        self.status_speed_label = QLabel("Speed: 0 KB/s")
        self.status_disk_label = QLabel("Free Disk: 0 GB")

        self.status_bar.addWidget(self.status_count_label, 1)
        self.status_bar.addPermanentWidget(self.status_speed_label)
        self.status_bar.addPermanentWidget(self.status_disk_label)

    def _setup_menus(self):
        menubar = self.menuBar()

        # 1. Tasks Menu
        tasks_menu = menubar.addMenu("&Tasks")
        add_act = tasks_menu.addAction("&Add New Download...")
        add_act.setShortcut(QKeySequence.StandardKey.New)
        add_act.triggered.connect(self.open_add_url_dialog)

        batch_act = tasks_menu.addAction("&Batch Download...")
        batch_act.triggered.connect(self.open_batch_download_dialog)

        tasks_menu.addSeparator()
        exit_act = tasks_menu.addAction("E&xit")
        exit_act.setShortcut(QKeySequence("Ctrl+Q"))
        exit_act.triggered.connect(self.quit_application)

        # 2. File Menu
        file_menu = menubar.addMenu("&File")
        resume_act = file_menu.addAction("&Resume Download")
        resume_act.triggered.connect(self._resume_selected)

        stop_act = file_menu.addAction("&Stop / Pause Download")
        stop_act.triggered.connect(self._pause_selected)

        stop_all_act = file_menu.addAction("Stop &All")
        stop_all_act.triggered.connect(self.stop_all_downloads)

        file_menu.addSeparator()
        del_act = file_menu.addAction("&Delete Selected")
        del_act.setShortcut(QKeySequence.StandardKey.Delete)
        del_act.triggered.connect(self._delete_selected)

        # 3. Downloads Menu
        dl_menu = menubar.addMenu("&Downloads")
        start_q_act = dl_menu.addAction("&Start Queue")
        start_q_act.triggered.connect(self.start_queue)

        stop_q_act = dl_menu.addAction("S&top Queue")
        stop_q_act.triggered.connect(self.stop_queue)

        dl_menu.addSeparator()
        scheduler_act = dl_menu.addAction("&Scheduler...")
        scheduler_act.triggered.connect(self.open_scheduler_dialog)

        options_act = dl_menu.addAction("&Options...")
        options_act.triggered.connect(self.open_options_dialog)

        browser_act = dl_menu.addAction("Register &Browser Integration...")
        browser_act.triggered.connect(self._register_browser_integration)

        # 4. Help Menu
        help_menu = menubar.addMenu("&Help")
        help_browser_act = help_menu.addAction("Register &Browser Integration...")
        help_browser_act.triggered.connect(self._register_browser_integration)
        help_menu.addSeparator()
        about_act = help_menu.addAction("&About PV-IDM")
        about_act.triggered.connect(self._show_about)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setIconSize(QSize(22, 22))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        btn_add = toolbar.addAction("➕ Add URL")
        btn_add.triggered.connect(self.open_add_url_dialog)

        toolbar.addSeparator()

        btn_resume = toolbar.addAction("▶ Resume")
        btn_resume.triggered.connect(self._resume_selected)

        btn_stop = toolbar.addAction("⏸ Stop")
        btn_stop.triggered.connect(self._pause_selected)

        btn_stop_all = toolbar.addAction("⏹ Stop All")
        btn_stop_all.triggered.connect(self.stop_all_downloads)

        toolbar.addSeparator()

        btn_delete = toolbar.addAction("❌ Delete")
        btn_delete.triggered.connect(self._delete_selected)

        toolbar.addSeparator()

        btn_options = toolbar.addAction("⚙ Options")
        btn_options.triggered.connect(self.open_options_dialog)

        btn_scheduler = toolbar.addAction("⏰ Scheduler")
        btn_scheduler.triggered.connect(self.open_scheduler_dialog)

        toolbar.addSeparator()

        btn_start_q = toolbar.addAction("▶ Start Queue")
        btn_start_q.triggered.connect(self.start_queue)

        btn_stop_q = toolbar.addAction("⏹ Stop Queue")
        btn_stop_q.triggered.connect(self.stop_queue)

    def _setup_events(self):
        # Create Qt thread bridge
        self.bridge = EngineEventBridge(self)
        self.bridge.download_progress.connect(self._on_engine_progress)
        self.bridge.segment_update.connect(self._on_engine_segment_update)
        self.bridge.download_started.connect(self._on_engine_download_started)
        self.bridge.download_paused.connect(self._on_engine_download_paused)
        self.bridge.download_completed.connect(self._on_engine_download_completed)
        self.bridge.download_error.connect(self._on_engine_download_error)
        self.bridge.download_requested.connect(self._handle_download_requested)
        self.bridge.show_gui.connect(self._on_engine_show_gui)

        # Connect engine event callbacks to bridge
        self.engine.register_listener("download_progress", lambda d: self.bridge.download_progress.emit(d))
        self.engine.register_listener("segment_update", lambda d: self.bridge.segment_update.emit(d))
        self.engine.register_listener("download_started", lambda d: self.bridge.download_started.emit(d))
        self.engine.register_listener("download_paused", lambda d: self.bridge.download_paused.emit(d))
        self.engine.register_listener("download_completed", lambda d: self.bridge.download_completed.emit(d))
        self.engine.register_listener("download_error", lambda d: self.bridge.download_error.emit(d))
        self.engine.register_listener("download_requested", lambda d: self.bridge.download_requested.emit(d))
        self.engine.register_listener("show_gui", lambda d: self.bridge.show_gui.emit(d))

    def _handle_download_requested(self, data: dict):
        try:
            url = data.get("url", "")
            if not url:
                return

            raw_filename = data.get("filename", "")
            headers = data.get("headers", {})
            quality = data.get("quality")
            if quality and "quality" not in headers:
                headers["quality"] = quality

            total_bytes = data.get("total_bytes", 0)
            category = data.get("category", "")
            if not category or category == "General":
                category = self.engine.category_manager.get_category_for_filename(raw_filename) if raw_filename else "General"

            dest_dir = self.engine.category_manager.get_destination_directory(category)
            save_path = data.get("save_path") or os.path.join(dest_dir, raw_filename or "download")

            # Create and display DownloadInfoDialog in foreground
            dlg = DownloadInfoDialog(
                url=url,
                filename=raw_filename,
                save_path=save_path,
                category=category,
                file_size=total_bytes,
                headers=headers,
                parent=None
            )
            dlg.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()

            if dlg.exec():
                res = dlg.get_data()
                start_imm = res.get("start_immediately", True)
                dl_id = self.engine.add_download(
                    url=res["url"],
                    filename=res["filename"],
                    save_path=res["save_path"],
                    category=res["category"],
                    headers=headers,
                    total_bytes=dlg.file_size,
                    start_immediately=start_imm
                )
                self.refresh_downloads()
                if start_imm and dl_id:
                    self._show_progress_dialog(dl_id)
                self.refresh_downloads()
        except Exception as e:
            print(f"[IDM Error] _handle_download_requested failed: {e}", file=sys.stderr)

    def _on_engine_show_gui(self, data: dict):
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_engine_download_started(self, data: dict):
        dl_id = data.get("download_id")
        if dl_id:
            # Open or update individual download progress window
            self._show_progress_dialog(dl_id)
            if dl_id in self.progress_dialogs:
                info = self.engine.get_download_info(dl_id)
                if info:
                    self.progress_dialogs[dl_id].update_progress(info)
            self.refresh_downloads()

    def _on_engine_download_paused(self, data: dict):
        dl_id = data.get("download_id")
        if dl_id and dl_id in self.progress_dialogs:
            info = self.engine.get_download_info(dl_id)
            if info:
                self.progress_dialogs[dl_id].update_progress(info)
        self.refresh_downloads()

    def _on_engine_download_completed(self, data: dict):
        dl_id = data.get("download_id")
        if dl_id and dl_id in self.progress_dialogs:
            info = self.engine.get_download_info(dl_id)
            if info:
                self.progress_dialogs[dl_id].update_progress(info)
        self.refresh_downloads()

    def _on_engine_download_error(self, data: dict):
        dl_id = data.get("download_id")
        if dl_id and dl_id in self.progress_dialogs:
            info = self.engine.get_download_info(dl_id)
            if info:
                self.progress_dialogs[dl_id].update_progress(info)
        self.refresh_downloads()

    def refresh_downloads(self):
        """Fetch updated downloads list and refresh table & stats."""
        downloads = self.engine.list_downloads(
            category=self.current_category,
            search=self.current_search
        )
        self.table.update_downloads(downloads)

        # Update category counts
        all_dls = self.engine.database.list_downloads()
        counts = {
            "All Downloads": len(all_dls),
            "Unfinished": sum(1 for d in all_dls if d["status"] != "completed"),
            "Finished": sum(1 for d in all_dls if d["status"] == "completed"),
            "Compressed": sum(1 for d in all_dls if d.get("category") == "Compressed"),
            "Documents": sum(1 for d in all_dls if d.get("category") == "Documents"),
            "Music": sum(1 for d in all_dls if d.get("category") == "Music"),
            "Programs": sum(1 for d in all_dls if d.get("category") == "Programs"),
            "Video": sum(1 for d in all_dls if d.get("category") == "Video"),
        }
        self.category_tree.update_counts(counts)

        # Status Bar Stats
        active_speed = sum(d.get("speed", 0) for d in downloads if d["status"] == "downloading")
        self.status_count_label.setText(f"Total: {len(downloads)} items (Active: {sum(1 for d in downloads if d['status'] == 'downloading')})")
        self.status_speed_label.setText(f"Transfer Speed: {format_speed(active_speed)}")
        free_space = self.engine.storage.get_free_space()
        self.status_disk_label.setText(f"Free Disk: {format_bytes(free_space)}")

        # Synchronize all active progress windows
        for did, dlg in list(self.progress_dialogs.items()):
            if dlg.isVisible():
                info = self.engine.get_download_info(did)
                if info:
                    dlg.update_progress(info)
                    if info.get("segments"):
                        dlg.update_segments(info["segments"])

    def open_add_url_dialog(self, default_url: str = ""):
        # Check clipboard for valid URL
        clipboard_text = QApplication.clipboard().text().strip()
        initial_url = default_url or (clipboard_text if clipboard_text.startswith(("http://", "https://", "ftp://")) else "")

        dialog = DownloadInfoDialog(url=initial_url, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            if data["url"]:
                dl_id = self.engine.add_download(
                    url=data["url"],
                    filename=data["filename"],
                    save_path=data["save_path"],
                    category=data["category"],
                    headers=dialog.headers,
                    total_bytes=dialog.file_size,
                    start_immediately=data["start_immediately"]
                )
                self.refresh_downloads()
                if data["start_immediately"]:
                    self._show_progress_dialog(dl_id)

    def open_batch_download_dialog(self):
        dialog = BatchDownloadDialog(self)
        if dialog.exec():
            urls = dialog.get_urls()
            for u in urls:
                self.engine.add_download(url=u, start_immediately=False)
            self.refresh_downloads()

    def open_options_dialog(self):
        dialog = OptionsDialog(self)
        if dialog.exec():
            self.refresh_downloads()

    def open_scheduler_dialog(self):
        dialog = QueueSchedulerDialog(self)
        dialog.exec()

    def start_queue(self):
        self.engine.start_queue("main")
        self.refresh_downloads()

    def stop_queue(self):
        self.engine.stop_queue("main")
        self.refresh_downloads()

    def stop_all_downloads(self):
        self.engine.stop_all()
        self.refresh_downloads()

    def _resume_selected(self):
        for dl_id in self.table.get_selected_download_ids():
            self.engine.resume_download(dl_id)
            self._show_progress_dialog(dl_id)
        self.refresh_downloads()

    def _pause_selected(self):
        for dl_id in self.table.get_selected_download_ids():
            self.engine.pause_download(dl_id)
        self.refresh_downloads()

    def _delete_selected(self, delete_files_default: bool = False):
        ids = self.table.get_selected_download_ids()
        if not ids:
            return
        
        first_fn = ""
        if len(ids) == 1:
            dl = self.engine.get_download_info(ids[0])
            first_fn = dl.get("filename", "") if dl else ""

        dlg = DeleteConfirmDialog(count=len(ids), filename=first_fn, delete_files_default=delete_files_default, parent=self)
        if dlg.exec():
            delete_files = dlg.delete_files_from_disk()
            for dl_id in ids:
                self.engine.delete_download(dl_id, delete_files=delete_files, move_to_trash=True)
            self.refresh_downloads()

    def _on_table_action(self, action: str, download_id: str):
        if action == "resume":
            self.engine.resume_download(download_id)
            self._show_progress_dialog(download_id)
        elif action == "pause":
            self.engine.pause_download(download_id)
        elif action == "redownload":
            dl = self.engine.get_download_info(download_id)
            if dl:
                self.engine.delete_download(download_id)
                new_id = self.engine.add_download(url=dl["url"], filename=dl["filename"], save_path=dl["save_path"])
                if new_id:
                    self._show_progress_dialog(new_id)
        elif action == "delete":
            self._delete_selected(delete_files_default=False)
        elif action == "delete_file":
            self._delete_selected(delete_files_default=True)
        self.refresh_downloads()

    def _on_download_double_clicked(self, download_id: str):
        self._show_progress_dialog(download_id)

    def _show_progress_dialog(self, download_id: str):
        try:
            dl = self.engine.get_download_info(download_id)
            if not dl:
                return

            if download_id not in self.progress_dialogs or not self.progress_dialogs[download_id].isVisible():
                dlg = DownloadProgressDialog(download_id, dl.get("filename", "Download"), save_path=dl.get("save_path", ""), parent=None)
                dlg.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
                dlg.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
                dlg.pause_requested.connect(self.engine.pause_download)
                dlg.resume_requested.connect(self.engine.resume_download)
                dlg.cancel_requested.connect(lambda did: self.engine.delete_download(did, delete_files=True))
                dlg.speed_limit_changed.connect(lambda did, limit: self._set_dl_speed_limit(did, limit))

                self.progress_dialogs[download_id] = dlg
                dlg.update_progress(dl)
                dlg.showNormal()
                dlg.show()
                dlg.raise_()
                dlg.activateWindow()
            else:
                dlg = self.progress_dialogs[download_id]
                dlg.update_progress(dl)
                dlg.showNormal()
                dlg.show()
                dlg.raise_()
                dlg.activateWindow()
        except Exception as e:
            print(f"[IDM GUI Error] _show_progress_dialog failed: {e}")

    def _set_dl_speed_limit(self, download_id: str, limit_bps: int):
        downloader = self.engine.active_downloaders.get(download_id)
        if downloader:
            downloader.set_speed_limit(limit_bps)

    def _on_engine_progress(self, stats: dict):
        try:
            dl_id = stats.get("download_id")
            if dl_id and dl_id in self.progress_dialogs:
                self.progress_dialogs[dl_id].update_progress(stats)
        except Exception as e:
            pass

    def _on_engine_segment_update(self, data: dict):
        try:
            dl_id = data.get("download_id")
            if dl_id and dl_id in self.progress_dialogs:
                self.progress_dialogs[dl_id].update_segments(data.get("segments", []))
        except Exception as e:
            pass

    def _on_category_selected(self, category: str):
        self.current_category = category
        self.refresh_downloads()

    def _on_queue_selected(self, queue_id: str):
        self.current_category = "All Downloads"
        self.refresh_downloads()

    def _on_search_changed(self, text: str):
        self.current_search = text.strip()
        self.refresh_downloads()

    def _show_about(self):
        import idm_core
        QMessageBox.about(
            self,
            "About PV-IDM",
            f"<h3>PV-IDM v{idm_core.__version__}</h3>"
            "<p>Internet Download Manager clone for Linux desktop environments.</p>"
            "<p>Features dynamic multi-segment connection allocation, browser download interception, "
            "floating video sniffer, queue scheduler, and native IPC.</p>"
            "<p><b>License:</b> GNU General Public License v3.0 (GPL-3.0)</p>"
        )

    def _register_browser_integration(self):
        """Install or register native messaging host for Chrome/Firefox browsers."""
        try:
            from idm_core.platform import register_native_messaging_host, resolve_native_host_binary
            current_host = resolve_native_host_binary()
            res = register_native_messaging_host(binary_path=current_host)
            targets_str = "\n".join(f" - {t}" for t in res.get("targets", []))
            manifest = res.get("manifest_path", "Manifest created")
            QMessageBox.information(
                self,
                "Browser Integration",
                f"Browser native messaging host registered successfully!\n\n"
                f"Manifest:\n{manifest}\n\n"
                f"Configured targets:\n{targets_str}\n\n"
                f"Please restart your browser or reload the IDM extension if needed."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Browser Integration Error",
                f"Failed to register browser integration:\n{e}"
            )

    def quit_application(self):
        self.engine.shutdown()
        QApplication.quit()

    def closeEvent(self, event):
        # Minimize to system tray or close
        self.hide()
        event.ignore()
