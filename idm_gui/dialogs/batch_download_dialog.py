"""
Batch URL Importer and Site Grabber Dialog
"""

from typing import List
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)


class BatchDownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Download - Add Multiple URLs")
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Paste download URLs (one per line):"))

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("https://example.com/file1.zip\nhttps://example.com/file2.mp4\n...")
        layout.addWidget(self.text_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_add = QPushButton("Add to Queue")
        self.btn_add.setDefault(True)
        self.btn_add.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def get_urls(self) -> List[str]:
        lines = self.text_edit.toPlainText().splitlines()
        return [line.strip() for line in lines if line.strip().startswith("http://") or line.strip().startswith("https://") or line.strip().startswith("ftp://")]
