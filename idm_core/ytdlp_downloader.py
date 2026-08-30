"""
Video Platform Stream Downloader using yt-dlp with Real-Time Telemetry & Progress Parsing
Handles downloading from YouTube, Vimeo, Dailymotion, Reddit, Twitter/X, Twitch, etc.
"""

import os
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional
from idm_core.config import Config


class YTDLPDownloader:
    def __init__(
        self,
        download_id: str,
        url: str,
        save_path: str,
        config: Optional[Config] = None,
        speed_limit: int = 0,
        headers: Optional[Dict[str, str]] = None,
        quality: Optional[str] = None,
        on_progress: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_segment_update: Optional[Callable[[str, List[dict]], None]] = None,
        on_complete: Optional[Callable[[str, str], None]] = None,
        on_error: Optional[Callable[[str, str], None]] = None,
        on_log: Optional[Callable[[str, str], None]] = None,
    ):
        self.download_id = download_id
        self.url = url
        self.save_path = save_path
        self.config = config or Config()
        self.speed_limit = speed_limit
        self.headers = headers or {}
        self.quality = quality
        self.on_progress = on_progress
        self.on_segment_update = on_segment_update
        self.on_complete = on_complete
        self.on_error = on_error
        self.on_log = on_log

        self.status = "idle"
        self.total_bytes = 0
        self.downloaded_bytes = 0
        self.speed = 0.0
        self.eta = 0.0

        self._process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.RLock()

    @staticmethod
    def is_ytdlp_available() -> bool:
        return shutil.which("yt-dlp") is not None or shutil.which("youtube-dl") is not None

    @staticmethod
    def is_video_platform_url(url: str) -> bool:
        """Check if URL points to a known streaming video platform."""
        lower = url.lower()
        domains = [
            "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
            "twitch.tv", "tiktok.com", "twitter.com", "x.com",
            "facebook.com", "fb.watch", "instagram.com", "reddit.com",
            "soundcloud.com", "bilibili.com"
        ]
        return any(d in lower for d in domains)

    def log(self, msg: str):
        if self.on_log:
            try:
                self.on_log(self.download_id, msg)
            except Exception:
                pass

    def start(self):
        with self._lock:
            if self.status == "downloading":
                return
            self.status = "downloading"
            self._stop_event.clear()
            self._pause_event.clear()

        threading.Thread(target=self._run_ytdlp, daemon=True).start()

    def pause(self):
        with self._lock:
            self.status = "paused"
            self._pause_event.set()
            if self._process:
                try:
                    self._process.terminate()
                except Exception:
                    pass

    def resume(self):
        self.start()

    def cancel(self):
        with self._lock:
            self.status = "cancelled"
            self._stop_event.set()
            if self._process:
                try:
                    self._process.kill()
                except Exception:
                    pass

    def _run_ytdlp(self):
        bin_name = "yt-dlp" if shutil.which("yt-dlp") else "youtube-dl"
        dest_dir = os.path.dirname(self.save_path)
        os.makedirs(dest_dir, exist_ok=True)

        cmd = [
            bin_name,
            "--newline",
            "--progress",
            "-N", "8",
            "--no-playlist",
            "--remote-components", "ejs:github",
            "-o", self.save_path,
        ]

        # Quality and format selection
        q_str = str(self.quality or self.headers.get("quality", "")).lower().strip()
        is_audio = "audio" in q_str or "mp3" in q_str or self.save_path.lower().endswith((".mp3", ".m4a", ".aac"))

        if is_audio:
            cmd.extend(["-f", "bestaudio/best", "-x", "--audio-format", "mp3"])
        elif q_str:
            height = "".join(filter(str.isdigit, q_str))
            if height:
                cmd.extend(["-f", f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best[height<={height}]/best"])
            else:
                cmd.extend(["-f", "bestvideo+bestaudio/best"])
        else:
            cmd.extend(["-f", "bestvideo+bestaudio/best"])

        # Add node js runtime if present
        if shutil.which("node"):
            cmd.extend(["--js-runtimes", f"node:{shutil.which('node')}"])

        # Add firefox browser cookies if available to authenticate streams
        firefox_dir = os.path.expanduser("~/.mozilla/firefox")
        if os.path.exists(firefox_dir):
            cmd.extend(["--cookies-from-browser", "firefox"])

        cmd.append(self.url)

        self.log(f"Starting video stream download with {bin_name} (quality: {q_str or 'best'})...")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Parse yt-dlp output for progress
            # e.g.: [download]  45.2% of  120.50MiB at  4.52MiB/s ETA 00:14
            for line in self._process.stdout:
                line = line.strip()
                if self._stop_event.is_set() or self._pause_event.is_set():
                    break
                self._parse_line(line)

            self._process.wait()
            ret_code = self._process.returncode

            if self._stop_event.is_set() or self._pause_event.is_set():
                return

            if ret_code == 0:
                self.status = "completed"
                # Check actual downloaded file
                final_path = self.save_path
                if not os.path.exists(final_path):
                    # Check if yt-dlp changed extension (e.g. .webm -> .mkv / .mp4)
                    base, _ = os.path.splitext(self.save_path)
                    for ext in [".mp4", ".mkv", ".webm", ".mp3", ".m4a"]:
                        if os.path.exists(base + ext):
                            final_path = base + ext
                            break

                file_size = os.path.getsize(final_path) if os.path.exists(final_path) else self.total_bytes
                self.downloaded_bytes = file_size
                self.total_bytes = file_size

                if self.on_progress:
                    self.on_progress(self.download_id, {
                        "status": "completed",
                        "downloaded_bytes": file_size,
                        "total_bytes": file_size,
                        "speed": 0,
                        "eta": 0,
                        "save_path": final_path
                    })

                if self.on_complete:
                    self.on_complete(self.download_id, final_path)
            else:
                self.status = "error"
                err_msg = f"yt-dlp exited with code {ret_code}"
                if self.on_error:
                    self.on_error(self.download_id, err_msg)

        except Exception as e:
            self.status = "error"
            self.log(f"yt-dlp execution error: {e}")
            if self.on_error:
                self.on_error(self.download_id, str(e))

    def _parse_line(self, line: str):
        if not line:
            return

        # [download]  45.2% of  120.50MiB at  4.52MiB/s ETA 00:14
        pct_match = re.search(r"(\d+(?:\.\d+)?)%", line)
        if pct_match:
            pct = float(pct_match.group(1))
            size_match = re.search(r"of\s+(?:~\s*)?(\d+(?:\.\d+)?)\s*([KMGT]?i?B)", line, re.I)
            if size_match:
                val = float(size_match.group(1))
                unit = size_match.group(2).upper()
                mult = {"B": 1, "KB": 1024, "KIB": 1024, "MB": 1024**2, "MIB": 1024**2, "GB": 1024**3, "GIB": 1024**3}.get(unit, 1024**2)
                self.total_bytes = int(val * mult)
                self.downloaded_bytes = int((pct / 100.0) * self.total_bytes)

            speed_match = re.search(r"at\s+(\d+(?:\.\d+)?)\s*([KMGT]?i?B)/s", line, re.I)
            if speed_match:
                s_val = float(speed_match.group(1))
                s_unit = speed_match.group(2).upper()
                s_mult = {"B": 1, "KB": 1024, "KIB": 1024, "MB": 1024**2, "MIB": 1024**2, "GB": 1024**3, "GIB": 1024**3}.get(s_unit, 1024**2)
                self.speed = s_val * s_mult

            eta_match = re.search(r"ETA\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", line)
            if eta_match:
                if eta_match.group(3):
                    self.eta = int(eta_match.group(1)) * 3600 + int(eta_match.group(2)) * 60 + int(eta_match.group(3))
                else:
                    self.eta = int(eta_match.group(1)) * 60 + int(eta_match.group(2))

            if self.on_progress:
                self.on_progress(self.download_id, {
                    "status": "downloading",
                    "downloaded_bytes": self.downloaded_bytes,
                    "total_bytes": self.total_bytes,
                    "speed": self.speed,
                    "eta": self.eta,
                    "save_path": self.save_path
                })
