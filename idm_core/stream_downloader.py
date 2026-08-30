"""
HLS (.m3u8) and DASH Stream Parser and Multi-Threaded Video Downloader
"""

import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional
from idm_core.config import Config
from idm_core.speed_limiter import SpeedLimiter
from idm_core.storage import StorageManager


class HLSParser:
    def __init__(self, m3u8_url: str, headers: Optional[Dict[str, str]] = None):
        self.m3u8_url = m3u8_url
        self.headers = headers or {}
        self.key_info = None  # Method, URI, IV

    def parse(self) -> List[str]:
        """Fetch and parse M3U8 manifest, returning list of resolved segment URLs."""
        content = self._fetch_text(self.m3u8_url)
        lines = [line.strip() for line in content.splitlines() if line.strip()]

        # Check if master playlist
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            variant_url = self._select_best_variant(lines, self.m3u8_url)
            content = self._fetch_text(variant_url)
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            base_url = variant_url
        else:
            base_url = self.m3u8_url

        segments = []
        for line in lines:
            if line.startswith("#"):
                if line.startswith("#EXT-X-KEY"):
                    self.key_info = line
                continue
            # Resolved segment URL
            seg_url = urllib.parse.urljoin(base_url, line)
            segments.append(seg_url)

        return segments

    def _select_best_variant(self, lines: List[str], base_url: str) -> str:
        """Find the highest bitrate/resolution variant stream in a master playlist."""
        best_bw = -1
        best_url = None

        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF"):
                match = re.search(r"BANDWIDTH=(\d+)", line)
                bw = int(match.group(1)) if match else 0
                if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                    if bw > best_bw or best_url is None:
                        best_bw = bw
                        best_url = urllib.parse.urljoin(base_url, lines[i + 1])

        return best_url or base_url

    def _fetch_text(self, url: str) -> str:
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="ignore")


class StreamDownloader:
    def __init__(
        self,
        download_id: str,
        url: str,
        save_path: str,
        storage: Optional[StorageManager] = None,
        config: Optional[Config] = None,
        num_connections: int = 8,
        speed_limit: int = 0,
        headers: Optional[Dict[str, str]] = None,
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
        self.storage = storage or StorageManager(self.config)
        self.num_connections = max(1, min(num_connections, 16))
        self.speed_limiter = SpeedLimiter(speed_limit)
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        }

        self.on_progress = on_progress
        self.on_segment_update = on_segment_update
        self.on_complete = on_complete
        self.on_error = on_error
        self.on_log = on_log

        self.status = "idle"  # idle, downloading, paused, completed, error
        self.total_segments = 0
        self.downloaded_segments = 0
        self.total_bytes = 0
        self.downloaded_bytes = 0
        self.segment_urls: List[str] = []
        self.segment_files: List[str] = []

        self._workers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.RLock()
        self._current_index = 0
        self._speed_bytes = 0
        self._speed_time = time.time()
        self.current_speed = 0.0

    def log(self, msg: str):
        if self.on_log:
            try:
                self.on_log(self.download_id, msg)
            except Exception:
                pass

    def start(self):
        """Parse stream manifest and launch concurrent segment workers."""
        with self._lock:
            if self.status == "downloading":
                return
            self.status = "downloading"
            self._stop_event.clear()
            self._pause_event.clear()

        threading.Thread(target=self._run_stream_engine, daemon=True).start()

    def _run_stream_engine(self):
        try:
            self.log(f"Parsing HLS stream manifest {self.url}...")
            parser = HLSParser(self.url, self.headers)
            self.segment_urls = parser.parse()
            self.total_segments = len(self.segment_urls)
            self.log(f"Extracted {self.total_segments} media segments.")

            if self.total_segments == 0:
                raise ValueError("No video segments found in manifest.")

            self.segment_files = [
                self.storage.get_temp_segment_path(self.download_id, i)
                for i in range(self.total_segments)
            ]

            # Spawn worker threads
            self._current_index = 0
            self._workers.clear()
            for w_id in range(self.num_connections):
                t = threading.Thread(target=self._worker_loop, args=(w_id,), daemon=True)
                self._workers.append(t)
                t.start()

            for t in self._workers:
                t.join()

            if self._stop_event.is_set() or self._pause_event.is_set() or self.status in ["paused", "cancelled"]:
                return

            self._finalize_stream()

        except Exception as e:
            if shutil.which("ffmpeg") and not self._stop_event.is_set():
                self.log(f"Direct segment parsing encountered '{e}'. Falling back to ffmpeg stream capture...")
                try:
                    os.makedirs(os.path.dirname(os.path.abspath(self.save_path)), exist_ok=True)
                    cmd = ["ffmpeg", "-y"]
                    if self.headers:
                        hdr_str = "".join(f"{k}: {v}\r\n" for k, v in self.headers.items() if k.lower() in ["user-agent", "referer", "cookie"])
                        if hdr_str:
                            cmd.extend(["-headers", hdr_str])
                    cmd.extend(["-i", self.url, "-c", "copy", self.save_path])
                    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
                    if res.returncode == 0 and os.path.exists(self.save_path) and os.path.getsize(self.save_path) > 0:
                        file_size = os.path.getsize(self.save_path)
                        self.downloaded_bytes = file_size
                        self.total_bytes = file_size
                        self.status = "completed"
                        self.log(f"Stream capture completed via ffmpeg: {self.save_path}")
                        if self.on_complete:
                            self.on_complete(self.download_id, self.save_path)
                        return
                except Exception as ex:
                    self.log(f"ffmpeg stream capture fallback failed: {ex}")

            self.status = "error"
            self.log(f"Stream download error: {e}")
            if self.on_error:
                self.on_error(self.download_id, str(e))

    def _worker_loop(self, worker_id: int):
        while not self._stop_event.is_set() and not self._pause_event.is_set():
            with self._lock:
                if self._current_index >= self.total_segments:
                    break
                idx = self._current_index
                self._current_index += 1

            seg_url = self.segment_urls[idx]
            seg_file = self.segment_files[idx]

            # Download chunk
            success = self._fetch_segment(seg_url, seg_file)
            if success:
                with self._lock:
                    self.downloaded_segments += 1
                    self._emit_progress()
            else:
                if self._stop_event.is_set() or self._pause_event.is_set():
                    break
                # Retry once
                time.sleep(1.0)
                if self._fetch_segment(seg_url, seg_file):
                    with self._lock:
                        self.downloaded_segments += 1
                        self._emit_progress()

    def _fetch_segment(self, url: str, target_file: str) -> bool:
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=self.config.network_timeout) as resp:
                data = resp.read()
                self.speed_limiter.acquire(len(data))
                with open(target_file, "wb") as f:
                    f.write(data)
                with self._lock:
                    self.downloaded_bytes += len(data)
                    self._speed_bytes += len(data)
                return True
        except Exception as e:
            self.log(f"Failed to fetch segment {url}: {e}")
            return False

    def _finalize_stream(self):
        self.log("All stream segments fetched. Storing and remuxing stream...")
        os.makedirs(os.path.dirname(os.path.abspath(self.save_path)), exist_ok=True)
        
        # Merge TS chunks
        raw_ts_path = self.save_path if self.save_path.endswith(".ts") else self.save_path + ".temp.ts"
        with open(raw_ts_path, "wb") as outfile:
            for s_file in self.segment_files:
                if os.path.exists(s_file):
                    with open(s_file, "rb") as infile:
                        shutil.copyfileobj(infile, outfile, length=1024 * 1024)

        # If destination is MP4/MKV and ffmpeg is available, remux losslessly
        if shutil.which("ffmpeg") and (self.save_path.endswith(".mp4") or self.save_path.endswith(".mkv")):
            self.log("Running ffmpeg stream copy into MP4 container...")
            try:
                cmd = ["ffmpeg", "-y", "-i", raw_ts_path, "-c", "copy", self.save_path]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if os.path.exists(raw_ts_path) and raw_ts_path != self.save_path:
                    os.remove(raw_ts_path)
            except Exception as e:
                self.log(f"ffmpeg remux failed ({e}), falling back to direct stream output.")
                if raw_ts_path != self.save_path and os.path.exists(raw_ts_path):
                    os.rename(raw_ts_path, self.save_path)
        elif raw_ts_path != self.save_path and os.path.exists(raw_ts_path):
            os.rename(raw_ts_path, self.save_path)

        self.storage.cleanup_temp(self.download_id)
        self.status = "completed"
        self.log(f"Stream download completed: {self.save_path}")

        if self.on_complete:
            try:
                self.on_complete(self.download_id, self.save_path)
            except Exception:
                pass

    def _emit_progress(self):
        now = time.time()
        elapsed = now - self._speed_time
        if elapsed >= 0.5:
            self.current_speed = self._speed_bytes / elapsed if elapsed > 0 else 0.0
            self._speed_bytes = 0
            self._speed_time = now

        stats = {
            "download_id": self.download_id,
            "status": self.status,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "speed": int(self.current_speed),
            "eta": 0,
            "segments_done": self.downloaded_segments,
            "total_segments": self.total_segments,
        }
        if self.on_progress:
            try:
                self.on_progress(self.download_id, stats)
            except Exception:
                pass

    def pause(self):
        with self._lock:
            self.status = "paused"
            self._pause_event.set()

    def cancel(self):
        with self._lock:
            self.status = "cancelled"
            self._stop_event.set()
            self._pause_event.set()
            self.storage.cleanup_temp(self.download_id)
