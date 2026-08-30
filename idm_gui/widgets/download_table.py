"""
IDM Download List Table Widget with Real-Time Stats and Context Menu
"""

import datetime
import os
import subprocess
from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont
from PyQt6.QtWidgets import (
    QHeaderView,
    QMenu,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
)


def format_bytes(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(num_bytes)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024.0
        i += 1
    return f"{val:.2f} {units[i]}"


def format_speed(bps: float) -> str:
    if bps <= 0:
        return "0 KB/s"
    return f"{format_bytes(int(bps))}/s"


def format_time(seconds: int) -> str:
    if seconds <= 0:
        return "--:--:--"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class DownloadTableWidget(QTableWidget):
    download_double_clicked = pyqtSignal(str)  # download_id
    action_requested = pyqtSignal(str, str)  # action_name, download_id

    COLUMNS = [
        "File Name",
        "Size",
        "Status",
        "Progress",
        "Time Left",
        "Transfer Rate",
        "Date Added",
        "Category",
        "URL"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._downloads_map: Dict[str, dict] = {}
        self._row_to_id: List[str] = []
        self._setup_table()

    def _setup_table(self):
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(3, 140)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.cellDoubleClicked.connect(self._on_double_click)

    def update_downloads(self, downloads: List[Dict[str, Any]]):
        """Re-populate or update table rows smoothly."""
        current_selected_ids = self.get_selected_download_ids()
        
        self.setRowCount(len(downloads))
        self._row_to_id = []
        self._downloads_map = {}

        for row, dl in enumerate(downloads):
            dl_id = dl["id"]
            self._row_to_id.append(dl_id)
            self._downloads_map[dl_id] = dl

            # 0: File Name
            fname_item = QTableWidgetItem(dl.get("filename", "download"))
            fname_item.setData(Qt.ItemDataRole.UserRole, dl_id)
            self.setItem(row, 0, fname_item)

            # 1: Size
            total = dl.get("total_bytes", 0)
            self.setItem(row, 1, QTableWidgetItem(format_bytes(total) if total > 0 else "Unknown"))

            # 2: Status
            status = dl.get("status", "queued").capitalize()
            status_item = QTableWidgetItem(status)
            if status.lower() == "downloading":
                status_item.setForeground(QColor("#48bb78"))
            elif status.lower() == "completed":
                status_item.setForeground(QColor("#4299e1"))
            elif status.lower() == "error":
                status_item.setForeground(QColor("#f56565"))
            self.setItem(row, 2, status_item)

            # 3: Progress Bar Widget
            dl_bytes = dl.get("downloaded_bytes", 0)
            pct = int((dl_bytes / total * 100)) if total > 0 else (100 if dl.get("status") == "completed" else 0)
            
            pbar = self.cellWidget(row, 3)
            if not isinstance(pbar, QProgressBar):
                pbar = QProgressBar()
                pbar.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setCellWidget(row, 3, pbar)
            pbar.setValue(pct)
            pbar.setFormat(f"{pct}%")

            # 4: Time Left
            eta = dl.get("eta", 0)
            self.setItem(row, 4, QTableWidgetItem(format_time(eta) if dl.get("status") == "downloading" else ""))

            # 5: Transfer Rate
            speed = dl.get("speed", 0)
            self.setItem(row, 5, QTableWidgetItem(format_speed(speed) if dl.get("status") == "downloading" else ""))

            # 6: Date Added
            created = dl.get("created_at", 0)
            date_str = datetime.datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M") if created else ""
            self.setItem(row, 6, QTableWidgetItem(date_str))

            # 7: Category
            self.setItem(row, 7, QTableWidgetItem(dl.get("category", "General")))

            # 8: URL
            self.setItem(row, 8, QTableWidgetItem(dl.get("url", "")))

        # Restore selection
        for row, dl_id in enumerate(self._row_to_id):
            if dl_id in current_selected_ids:
                self.selectRow(row)

    def get_selected_download_ids(self) -> List[str]:
        rows = set(index.row() for index in self.selectedIndexes())
        return [self._row_to_id[r] for r in rows if r < len(self._row_to_id)]

    def _on_double_click(self, row: int, col: int):
        if row < len(self._row_to_id):
            dl_id = self._row_to_id[row]
            dl = self._downloads_map.get(dl_id)
            if dl and dl.get("status") == "completed":
                path = dl.get("save_path")
                if path and os.path.exists(path):
                    try:
                        subprocess.Popen(["xdg-open", path])
                        return
                    except Exception:
                        pass
            self.download_double_clicked.emit(dl_id)

    def _show_context_menu(self, pos: QPoint):
        selected_ids = self.get_selected_download_ids()
        if not selected_ids:
            return

        menu = QMenu(self)
        first_id = selected_ids[0]
        first_dl = self._downloads_map.get(first_id, {})

        open_act = menu.addAction("▶ Open File")
        folder_act = menu.addAction("📂 Open Folder")
        menu.addSeparator()

        resume_act = menu.addAction("▶ Resume")
        pause_act = menu.addAction("⏸ Pause / Stop")
        redownload_act = menu.addAction("🔄 Redownload")
        menu.addSeparator()

        delete_list_act = menu.addAction("❌ Delete from List")
        delete_file_act = menu.addAction("🗑 Delete from Disk")
        menu.addSeparator()

        copy_url_act = menu.addAction("📋 Copy Download URL")
        props_act = menu.addAction("ℹ Properties")

        action = menu.exec(self.mapToGlobal(pos))
        if not action:
            return

        for dl_id in selected_ids:
            if action == open_act:
                dl = self._downloads_map.get(dl_id)
                if dl and dl.get("save_path") and os.path.exists(dl["save_path"]):
                    subprocess.Popen(["xdg-open", dl["save_path"]])
            elif action == folder_act:
                dl = self._downloads_map.get(dl_id)
                if dl and dl.get("save_path"):
                    folder = os.path.dirname(dl["save_path"])
                    subprocess.Popen(["xdg-open", folder])
            elif action == resume_act:
                self.action_requested.emit("resume", dl_id)
            elif action == pause_act:
                self.action_requested.emit("pause", dl_id)
            elif action == redownload_act:
                self.action_requested.emit("redownload", dl_id)
            elif action == delete_list_act:
                self.action_requested.emit("delete", dl_id)
            elif action == delete_file_act:
                self.action_requested.emit("delete_file", dl_id)
            elif action == copy_url_act:
                dl = self._downloads_map.get(dl_id)
                if dl:
                    from PyQt6.QtWidgets import QApplication
                    QApplication.clipboard().setText(dl.get("url", ""))
            elif action == props_act:
                self.download_double_clicked.emit(dl_id)
