"""
Video Stream Quality and Format Picker Dialog
"""

from typing import Any, Dict, List
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class VideoDownloadDialog(QDialog):
    def __init__(self, media_url: str = "", title: str = "", formats: List[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Video Stream")
        self.setMinimumWidth(480)
        self.media_url = media_url
        self.formats = formats or [
            {"label": "Full HD 1080p (MP4)", "format": "mp4", "quality": "1080p"},
            {"label": "HD 720p (MP4)", "format": "mp4", "quality": "720p"},
            {"label": "SD 480p (MP4)", "format": "mp4", "quality": "480p"},
            {"label": "Audio Only (MP3)", "format": "mp3", "quality": "audio"}
        ]

        self._setup_ui(title)

    def _setup_ui(self, title: str):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.title_edit = QLineEdit(title or "Web Video")
        form.addRow("Title:", self.title_edit)

        self.format_combo = QComboBox()
        for f in self.formats:
            self.format_combo.addItem(f["label"], f)
        form.addRow("Quality / Format:", self.format_combo)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_download = QPushButton("Start Download")
        self.btn_download.setDefault(True)
        self.btn_download.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def get_selection(self) -> dict:
        selected_fmt = self.format_combo.currentData() or {}
        return {
            "url": self.media_url,
            "title": self.title_edit.text().strip(),
            "format": selected_fmt.get("format", "mp4"),
            "quality": selected_fmt.get("quality", "1080p")
        }
