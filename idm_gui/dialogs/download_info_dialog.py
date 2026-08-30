"""
Download File Info Interception and URL Input Dialog
"""

import os
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class DownloadInfoDialog(QDialog):
    def __init__(
        self,
        url: str = "",
        filename: str = "",
        save_path: str = "",
        category: str = "General",
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Download File Info")
        self.setMinimumWidth(500)
        self.start_immediately = True

        self._setup_ui(url, filename, save_path, category)

    def _setup_ui(self, url: str, filename: str, save_path: str, category: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # URL
        self.url_edit = QLineEdit(url)
        form.addRow("URL:", self.url_edit)

        # Category
        self.category_combo = QComboBox()
        self.category_combo.addItems(["General", "Compressed", "Documents", "Music", "Programs", "Video"])
        if category in ["General", "Compressed", "Documents", "Music", "Programs", "Video"]:
            self.category_combo.setCurrentText(category)
        form.addRow("Category:", self.category_combo)

        # Save As
        save_layout = QHBoxLayout()
        self.save_edit = QLineEdit(save_path or os.path.expanduser(f"~/Downloads/{filename}"))
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._on_browse)
        save_layout.addWidget(self.save_edit)
        save_layout.addWidget(self.browse_btn)
        form.addRow("Save As:", save_layout)

        layout.addLayout(form)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_later = QPushButton("Download Later")
        self.btn_later.clicked.connect(self._on_download_later)

        self.btn_now = QPushButton("Start Download")
        self.btn_now.setDefault(True)
        self.btn_now.clicked.connect(self._on_download_now)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_later)
        btn_layout.addWidget(self.btn_now)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _on_browse(self):
        current = self.save_edit.text()
        initial_dir = os.path.dirname(current) if current else os.path.expanduser("~/Downloads")
        initial_file = os.path.basename(current) if current else ""
        chosen, _ = QFileDialog.getSaveFileName(self, "Save File As", os.path.join(initial_dir, initial_file))
        if chosen:
            self.save_edit.setText(chosen)

    def _on_download_now(self):
        self.start_immediately = True
        self.accept()

    def _on_download_later(self):
        self.start_immediately = False
        self.accept()

    def get_data(self) -> dict:
        return {
            "url": self.url_edit.text().strip(),
            "save_path": self.save_edit.text().strip(),
            "filename": os.path.basename(self.save_edit.text().strip()),
            "category": self.category_combo.currentText(),
            "start_immediately": self.start_immediately
        }
