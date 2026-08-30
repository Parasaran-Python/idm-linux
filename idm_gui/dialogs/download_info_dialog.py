"""
IDM Linux - Download File Info Dialog
Classic IDM-style prompt for URL, Save Location, Category, File Size, and Download Now / Later actions.
"""

import os
import re
import threading
import urllib.parse
import urllib.request
from typing import Optional, Dict
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from idm_gui.widgets.download_table import format_bytes


class ProbeWorker(QObject):
    probed = pyqtSignal(object, str)  # 64-bit size, filename

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        super().__init__()
        self.url = url
        self.headers = headers or {}

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            if not self.url or not self.url.startswith(("http://", "https://", "ftp://")):
                return

            # 1. Video Platform URLs (YouTube, Vimeo, Twitch, etc.)
            from idm_core.ytdlp_downloader import YTDLPDownloader
            if YTDLPDownloader.is_ytdlp_available() and (
                YTDLPDownloader.is_video_platform_url(self.url) or bool(self.headers.get("quality"))
            ):
                quality = self.headers.get("quality")
                info = YTDLPDownloader.probe_media_info(self.url, quality=quality)
                size = info.get("filesize", 0)
                filename = info.get("filename", "")
                if size > 0 or filename:
                    self.probed.emit(size, filename)
                return

            # 2. HLS Video Stream URLs (.m3u8)
            if ".m3u8" in self.url.lower():
                from idm_core.stream_downloader import HLSParser
                info = HLSParser.probe_stream_info(self.url, headers=self.headers)
                size = info.get("filesize", 0)
                if size > 0:
                    self.probed.emit(size, "")
                return

            # 3. Standard HTTP/HTTPS/FTP URLs (HEAD / Range Probe)
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Accept": "*/*",
                **self.headers
            }
            req = urllib.request.Request(self.url, headers=headers)
            req.get_method = lambda: "HEAD"
            size = 0
            filename = ""
            try:
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    cl = resp.headers.get("Content-Length")
                    if cl and cl.isdigit():
                        size = int(cl)
                    cd = resp.headers.get("Content-Disposition", "")
                    if "filename=" in cd:
                        m = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^";\n\r]+)["\']?', cd, re.I)
                        if m:
                            filename = m.group(1).strip()
            except Exception:
                try:
                    req_get = urllib.request.Request(self.url, headers={**headers, "Range": "bytes=0-0"})
                    with urllib.request.urlopen(req_get, timeout=3.5) as resp:
                        cr = resp.headers.get("Content-Range", "")
                        if "/" in cr:
                            tot = cr.split("/")[-1].strip()
                            if tot.isdigit():
                                size = int(tot)
                        elif resp.headers.get("Content-Length", "").isdigit():
                            size = int(resp.headers.get("Content-Length"))
                        cd = resp.headers.get("Content-Disposition", "")
                        if "filename=" in cd:
                            m = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^";\n\r]+)["\']?', cd, re.I)
                            if m:
                                filename = m.group(1).strip()
                except Exception:
                    pass

            if size > 0 or filename:
                self.probed.emit(size, filename)
        except Exception:
            pass


class DownloadInfoDialog(QDialog):
    def __init__(
        self,
        url: str = "",
        filename: str = "",
        save_path: str = "",
        category: str = "General",
        file_size: int = 0,
        headers: Optional[dict] = None,
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Download File Info")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setMinimumWidth(560)
        self.start_immediately = True
        self.headers = headers or {}
        self.file_size = file_size
        self.probe_worker: Optional[ProbeWorker] = None

        self._setup_ui(url, filename, save_path, category, file_size)

        if self.file_size <= 0 and url:
            self._start_probe(url)

    def _start_probe(self, url: str):
        self.probe_worker = ProbeWorker(url, self.headers)
        self.probe_worker.probed.connect(self._on_probed)
        self.probe_worker.start()

    def _on_probed(self, size: int, filename: str):
        if size > 0:
            self.file_size = size
            self.size_label.setText(format_bytes(size))
        if filename:
            cur_path = self.save_edit.text()
            cur_dir = os.path.dirname(cur_path) if cur_path else os.path.expanduser("~/Downloads")
            cur_fn = os.path.basename(cur_path)
            if not cur_fn or cur_fn in ["download", "videoplayback", "stream"]:
                self.save_edit.setText(os.path.join(cur_dir, filename))

    def _setup_ui(self, url: str, filename: str, save_path: str, category: str, file_size: int):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header Info Banner
        header_box = QFrame()
        header_box.setStyleSheet("background: #1b2631; border: 1px solid #2e4053; border-radius: 6px; padding: 6px;")
        header_layout = QHBoxLayout(header_box)
        header_icon = QLabel("📥")
        header_icon.setStyleSheet("font-size: 24px;")
        header_title = QLabel("<b>Internet Download Manager</b> - File Download Information")
        header_title.setStyleSheet("font-size: 13px; color: #5dade2;")
        header_layout.addWidget(header_icon)
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        layout.addWidget(header_box)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        # URL
        self.url_edit = QLineEdit(url)
        self.url_edit.setPlaceholderText("https://example.com/file.zip")
        form.addRow("<b>URL:</b>", self.url_edit)

        # Category
        self.category_combo = QComboBox()
        self.category_combo.addItems(["General", "Compressed", "Documents", "Music", "Programs", "Video"])
        if category in ["General", "Compressed", "Documents", "Music", "Programs", "Video"]:
            self.category_combo.setCurrentText(category)
        form.addRow("<b>Category:</b>", self.category_combo)

        # Save As
        save_layout = QHBoxLayout()
        default_save = save_path or os.path.expanduser(f"~/Downloads/{filename or 'download'}")
        self.save_edit = QLineEdit(default_save)
        self.browse_btn = QPushButton("📁 Browse...")
        self.browse_btn.clicked.connect(self._on_browse)
        save_layout.addWidget(self.save_edit)
        save_layout.addWidget(self.browse_btn)
        form.addRow("<b>Save As:</b>", save_layout)

        # File Size Info
        size_text = format_bytes(file_size) if file_size > 0 else "Unknown (will probe on start)"
        self.size_label = QLabel(size_text)
        self.size_label.setStyleSheet("color: #f4d03f; font-weight: bold;")
        form.addRow("<b>File Size:</b>", self.size_label)

        layout.addLayout(form)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2e4053;")
        layout.addWidget(sep)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_later = QPushButton("⏱ Download Later")
        self.btn_later.setToolTip("Add to queue list without starting download now")
        self.btn_later.clicked.connect(self._on_download_later)

        self.btn_now = QPushButton("📥 Start Download")
        self.btn_now.setDefault(True)
        self.btn_now.setStyleSheet("background: #1b4f72; color: #ffffff; font-weight: bold; padding: 6px 14px;")
        self.btn_now.clicked.connect(self._on_download_now)

        self.btn_cancel = QPushButton("✖ Cancel")
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
