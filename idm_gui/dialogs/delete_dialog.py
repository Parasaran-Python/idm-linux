"""
IDM Linux - Delete Download Confirmation Dialog
Allows removing from list or moving downloaded files to system Trash.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class DeleteConfirmDialog(QDialog):
    def __init__(self, count: int = 1, filename: str = "", delete_files_default: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delete Download" if count == 1 else "Delete Selected Downloads")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        if count == 1:
            name_str = f"<b>{filename}</b>" if filename else "this download"
            msg = f"Are you sure you want to remove {name_str} from the download list?"
        else:
            msg = f"Are you sure you want to remove <b>{count} selected downloads</b> from the list?"

        label = QLabel(msg)
        label.setWordWrap(True)
        layout.addWidget(label)

        self.trash_check = QCheckBox("🗑 Also delete downloaded file(s) from disk (move to Trash)")
        self.trash_check.setStyleSheet("font-weight: bold; color: #f6ad55; margin-top: 4px;")
        self.trash_check.setChecked(delete_files_default)
        layout.addWidget(self.trash_check)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_ok = QPushButton("Delete")
        self.btn_ok.setStyleSheet("background-color: #e53e3e; color: white; font-weight: bold; padding: 6px 18px;")
        self.btn_ok.clicked.connect(self.accept)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_ok)
        layout.addLayout(btn_box)

    def delete_files_from_disk(self) -> bool:
        return self.trash_check.isChecked()
