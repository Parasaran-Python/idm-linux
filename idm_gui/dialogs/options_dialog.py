"""
IDM Linux Configuration and Options Dialog
"""

import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class OptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IDM Configuration & Options")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Tab 1: Connection
        conn_tab = QWidget()
        conn_layout = QVBoxLayout(conn_tab)

        conn_box = QGroupBox("Connection Settings")
        conn_form = QFormLayout(conn_box)

        self.connections_spin = QSpinBox()
        self.connections_spin.setRange(1, 32)
        self.connections_spin.setValue(8)
        conn_form.addRow("Default max connections per download:", self.connections_spin)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(30)
        conn_form.addRow("Connection timeout (seconds):", self.timeout_spin)

        conn_layout.addWidget(conn_box)
        conn_layout.addStretch()
        tabs.addTab(conn_tab, "🌐 Connection")

        # Tab 2: File Types
        types_tab = QWidget()
        types_layout = QVBoxLayout(types_tab)

        types_box = QGroupBox("Browser Interception File Extensions")
        types_box_layout = QVBoxLayout(types_box)
        types_box_layout.addWidget(QLabel("Automatically intercept the following file extensions:"))
        
        self.intercept_edit = QPlainTextEdit(
            "3GP 7Z AAC ACE AIFF APK APPIMAGE ARJ ASF AVI BIN BZ2 DEB DMG DOC DOCX EPUB EXE "
            "FLAC FLV GZ ISO JAR M4A M4V MKV MOV MP3 MP4 MPA MPE MPEG MPG MSI OGG OPUS PDF "
            "PKG PPT PPTX RAR RPM RTF SH TAR TGZ TS TXT WAV WEBM WMA WMV XLS XLSX XZ ZIP ZST"
        )
        self.intercept_edit.setFixedHeight(90)
        types_box_layout.addWidget(self.intercept_edit)

        types_box_layout.addWidget(QLabel("Do NOT intercept for the following extensions:"))
        self.ignore_edit = QLineEdit("HTML HTM PHP ASP ASPX JSP CSS JS JSON XML")
        types_box_layout.addWidget(self.ignore_edit)

        types_layout.addWidget(types_box)
        types_layout.addStretch()
        tabs.addTab(types_tab, "📁 File Types")

        # Tab 3: Save To
        save_tab = QWidget()
        save_layout = QVBoxLayout(save_tab)

        dir_box = QGroupBox("Default Download Directory")
        dir_form = QFormLayout(dir_box)

        path_layout = QHBoxLayout()
        self.dir_edit = QLineEdit(os.path.expanduser("~/Downloads"))
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_dir)
        path_layout.addWidget(self.dir_edit)
        path_layout.addWidget(self.btn_browse)

        dir_form.addRow("Save files to:", path_layout)
        save_layout.addWidget(dir_box)
        save_layout.addStretch()
        tabs.addTab(save_tab, "💾 Save To")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_ok = QPushButton("OK")
        self.btn_ok.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _browse_dir(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.dir_edit.text())
        if chosen:
            self.dir_edit.setText(chosen)
