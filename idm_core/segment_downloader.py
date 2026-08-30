"""
High-Performance Multi-Segment HTTP/HTTPS Range Downloader with Dynamic Re-segmentation
"""

import os
import re
import socket
import ssl
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional
from idm_core.config import Config
from idm_core.dynamic_allocator import DynamicAllocator, Segment
from idm_core.speed_limiter import SpeedLimiter
from idm_core.storage import StorageManager


class SegmentDownloader:
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
        min_split_size: Optional[int] = None,
        saved_segments: Optional[List[dict]] = None,
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
        self.num_connections = max(1, min(num_connections, 32))
        self.speed_limiter = SpeedLimiter(speed_limit)
        self.headers = headers or {}
        self.min_split_size = min_split_size if min_split_size is not None else self.config.min_split_size

        self.on_progress = on_progress
        self.on_segment_update = on_segment_update
        self.on_complete = on_complete
        self.on_error = on_error
        self.on_log = on_log

        self.status = "idle"  # idle, probing, downloading, paused, completed, error, cancelled
        self.total_bytes = 0
        self.resumable = True
        self.filename = os.path.basename(save_path) or "download"
        self.final_url = url
        self.error_msg = ""

        self.allocator: Optional[DynamicAllocator] = None
        self._saved_segments = saved_segments

        self._workers: List[threading.Thread] = []
        self._stats_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.RLock()
        self._finalized = False

        self._speed_window_bytes = 0
        self._speed_window_time = time.time()
        self.current_speed = 0.0
        self.eta = 0

    def log(self, msg: str):
        if self.on_log:
            try:
                self.on_log(self.download_id, msg)
            except Exception:
                pass

    def probe(self) -> Dict[str, Any]:
        """Query server for Content-Length, Accept-Ranges, and filename."""
        old_status = self.status
        self.status = "probing"
        self.log(f"Probing {self.url}...")
        
        req = urllib.request.Request(self.url, headers=self._build_headers())
        info = {
            "status_code": 200,
            "content_length": 0,
            "resumable": False,
            "filename": self.filename,
            "content_type": "",
            "final_url": self.url,
        }

        try:
            req.get_method = lambda: "HEAD"
            with urllib.request.urlopen(req, timeout=self.config.network_timeout) as resp:
                info["status_code"] = resp.status
                info["final_url"] = resp.geturl()
                self.final_url = resp.geturl()
                headers = resp.headers

                cl = headers.get("Content-Length")
                if cl and cl.isdigit():
                    info["content_length"] = int(cl)
                    self.total_bytes = int(cl)

                accept_ranges = headers.get("Accept-Ranges", "").lower()
                cr = headers.get("Content-Range", "")
                if "bytes" in accept_ranges or cr:
                    info["resumable"] = True
                    self.resumable = True
                elif self.total_bytes > 0:
                    info["resumable"] = self._check_range_support()
                    self.resumable = info["resumable"]

                info["content_type"] = headers.get("Content-Type", "")
                
                cd = headers.get("Content-Disposition", "")
                if cd:
                    fname = self._extract_filename_from_cd(cd)
                    if fname:
                        info["filename"] = fname
                        self.filename = fname
                elif not os.path.basename(self.save_path):
                    url_fname = os.path.basename(urllib.parse.urlparse(self.final_url).path)
                    if url_fname:
                        info["filename"] = url_fname
                        self.filename = url_fname

        except Exception as e:
            self.log(f"HEAD request failed ({e}), falling back to GET probe...")
            try:
                req_get = urllib.request.Request(self.url, headers=self._build_headers({"Range": "bytes=0-0"}))
                with urllib.request.urlopen(req_get, timeout=self.config.network_timeout) as resp:
                    info["status_code"] = resp.status
                    info["final_url"] = resp.geturl()
                    self.final_url = resp.geturl()
                    headers = resp.headers
                    cr = headers.get("Content-Range", "")
                    if cr and "/" in cr:
                        total_str = cr.split("/")[-1]
                        if total_str.isdigit():
                            info["content_length"] = int(total_str)
                            self.total_bytes = int(total_str)
                            info["resumable"] = True
                            self.resumable = True
                    else:
                        cl = headers.get("Content-Length")
                        if cl and cl.isdigit():
                            info["content_length"] = int(cl)
                            self.total_bytes = int(cl)
            except Exception as e2:
                self.log(f"Probe GET error: {e2}")

        if old_status != "probing":
            self.status = old_status

        return info

    def start(self):
        """Start or resume multi-segmented download."""
        with self._lock:
            if self.status == "downloading":
                return
            self._stop_event.clear()
            self._pause_event.clear()
            self._finalized = False

            if self.total_bytes == 0:
                self.probe()

            self.status = "downloading"

            if not self.allocator:
                if self._saved_segments:
                    self.allocator = DynamicAllocator(
                        total_bytes=self.total_bytes,
                        min_split_size=self.min_split_size,
                        saved_segments=self._saved_segments
                    )
                else:
                    conns = self.num_connections if self.resumable else 1
                    self.allocator = DynamicAllocator(
                        total_bytes=self.total_bytes,
                        num_connections=conns,
                        min_split_size=self.min_split_size
                    )

            # Assign temporary paths to segments
            for seg in self.allocator.get_segments():
                if not seg.temp_path:
                    seg.temp_path = self.storage.get_temp_segment_path(self.download_id, seg.index)

            # Spawn worker threads
            worker_count = self.num_connections if self.resumable and self.total_bytes > 0 else 1
            self._workers.clear()
            for w_id in range(worker_count):
                t = threading.Thread(target=self._worker_loop, args=(w_id,), daemon=True)
                self._workers.append(t)
                t.start()

            # Start stats and telemetry monitor
            self._speed_window_bytes = 0
            self._speed_window_time = time.time()
            self._stats_thread = threading.Thread(target=self._stats_monitor_loop, daemon=True)
            self._stats_thread.start()

    def pause(self):
        """Pause active download."""
        with self._lock:
            if self.status not in ["downloading", "probing"]:
                return
            self.status = "paused"
            self._pause_event.set()
            self.log(f"Pausing download {self.download_id}...")

    def resume(self):
        """Resume paused download."""
        self.start()

    def cancel(self):
        """Cancel download and clean up temp files."""
        with self._lock:
            self.status = "cancelled"
            self._stop_event.set()
            self._pause_event.set()
            self.storage.cleanup_temp(self.download_id)

    def set_speed_limit(self, limit_bps: int):
        self.speed_limiter.set_rate_limit(limit_bps)

    def _worker_loop(self, worker_id: int):
        """Worker thread executing segment downloads with dynamic chunk splitting."""
        self.log(f"Worker {worker_id} started.")
        
        while not self._stop_event.is_set() and not self._pause_event.is_set() and self.status not in ["paused", "cancelled"]:
            segment: Optional[Segment] = None

            # 1. Look for a queued or errored segment
            with self._lock:
                for s in self.allocator.get_segments():
                    if s.status in ["queued", "error"]:
                        segment = s
                        self.allocator.set_segment_status(s.index, "downloading", worker_id=worker_id)
                        break

                # 2. If no queued segment, try dynamic sub-chunk split from busiest worker
                if segment is None and self.resumable and self.total_bytes > 0:
                    split_res = self.allocator.request_subchunk_split(self.min_split_size)
                    if split_res:
                        src_idx, new_seg = split_res
                        new_seg.temp_path = self.storage.get_temp_segment_path(self.download_id, new_seg.index)
                        self.allocator.set_segment_status(new_seg.index, "downloading", worker_id=worker_id)
                        segment = new_seg
                        self.log(f"Worker {worker_id}: dynamically split chunk from segment {src_idx} -> new segment {new_seg.index} [{new_seg.start_byte}-{new_seg.end_byte}]")

            if segment is None:
                if self.allocator.is_complete():
                    self._check_and_finalize()
                    break
                time.sleep(0.1)
                continue

            # 3. Download the assigned segment
            success = self._download_segment(worker_id, segment)
            if success and not self._pause_event.is_set() and not self._stop_event.is_set() and self.status not in ["paused", "cancelled"]:
                self.allocator.mark_completed(segment.index)
                if self.allocator.is_complete():
                    self._check_and_finalize()
                    break
            else:
                if self._pause_event.is_set() or self._stop_event.is_set() or self.status in ["paused", "cancelled"]:
                    break
                # Segment was interrupted or had a network glitch: requeue it so it can be resumed
                with self._lock:
                    if segment.status != "completed":
                        self.allocator.set_segment_status(segment.index, "queued", worker_id=None)
                time.sleep(0.5)

        self.log(f"Worker {worker_id} stopped.")

    def _download_segment(self, worker_id: int, segment: Segment) -> bool:
        """Fetch byte range over HTTP and write to segment temporary file."""
        # Align segment.current_byte with the actual bytes present on disk to avoid drift on pause/resume
        if segment.temp_path and os.path.exists(segment.temp_path):
            actual_size = os.path.getsize(segment.temp_path)
            expected_max = segment.end_byte - segment.start_byte + 1 if segment.end_byte >= 0 else actual_size
            if actual_size > expected_max and expected_max >= 0:
                with open(segment.temp_path, "r+b") as f:
                    f.truncate(expected_max)
                actual_size = expected_max
            segment.current_byte = segment.start_byte + actual_size

        if segment.end_byte >= 0 and segment.current_byte > segment.end_byte:
            return True

        headers = self._build_headers()
        if self.resumable and segment.end_byte >= 0:
            headers["Range"] = f"bytes={segment.current_byte}-{segment.end_byte}"
        elif self.resumable and segment.current_byte > 0:
            headers["Range"] = f"bytes={segment.current_byte}-"

        try:
            req = urllib.request.Request(self.final_url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.config.network_timeout) as resp:
                while not self._stop_event.is_set() and not self._pause_event.is_set() and self.status not in ["paused", "cancelled"]:
                    if segment.end_byte >= 0 and segment.current_byte > segment.end_byte:
                        return True

                    to_read = self.config.chunk_read_size
                    if segment.end_byte >= 0:
                        remaining = segment.end_byte - segment.current_byte + 1
                        if remaining <= 0:
                            return True
                        to_read = min(to_read, remaining)

                    chunk = resp.read(to_read)
                    if not chunk:
                        return True

                    self.speed_limiter.acquire(len(chunk))
                    self.storage.append_segment_chunk(segment.temp_path, chunk)
                    chunk_len = len(chunk)
                    
                    with self._lock:
                        self.allocator.update_progress(segment.index, chunk_len)
                        self._speed_window_bytes += chunk_len

            if self._stop_event.is_set() or self._pause_event.is_set() or self.status in ["paused", "cancelled"]:
                return False

            if segment.end_byte >= 0 and segment.current_byte <= segment.end_byte:
                return False

            return True

        except Exception as e:
            self.log(f"Worker {worker_id} segment {segment.index} error ({e}), will retry...")
            with self._lock:
                self.allocator.set_segment_status(segment.index, "queued", error_msg=str(e))
            return False

    def _check_and_finalize(self):
        """Merge segments in ascending start_byte order and complete download."""
        with self._lock:
            if self._finalized:
                return
            if not self.allocator or not self.allocator.is_complete():
                return
            if self._stop_event.is_set() or self._pause_event.is_set() or self.status in ["paused", "cancelled"]:
                return
            self._finalized = True
            self.status = "completed"

        self.log(f"All segments downloaded. Assembling file to {self.save_path}...")
        sorted_segments = sorted(self.allocator.get_segments(), key=lambda s: s.start_byte)
        segment_items = [(s.temp_path, s.total_size) for s in sorted_segments if s.temp_path and os.path.exists(s.temp_path)]
        
        self.storage.merge_segments(
            download_id=self.download_id,
            segment_files=segment_items,
            destination_path=self.save_path,
            total_bytes=self.total_bytes if self.total_bytes > 0 else None
        )
        self.storage.cleanup_temp(self.download_id)
        self.log("Download finished successfully.")

        if self.on_complete:
            try:
                self.on_complete(self.download_id, self.save_path)
            except Exception as e:
                self.log(f"on_complete callback error: {e}")

    def _stats_monitor_loop(self):
        """Calculate transfer rate, ETA, and trigger UI callbacks periodically."""
        while not self._stop_event.is_set() and not self._pause_event.is_set() and self.status == "downloading":
            time.sleep(0.3)
            now = time.time()
            elapsed = now - self._speed_window_time
            if elapsed >= 0.3:
                with self._lock:
                    bytes_in_window = self._speed_window_bytes
                    self._speed_window_bytes = 0
                    self._speed_window_time = now

                    self.current_speed = bytes_in_window / elapsed if elapsed > 0 else 0.0
                    downloaded = self.allocator.get_total_downloaded() if self.allocator else 0
                    
                    if self.current_speed > 0 and self.total_bytes > downloaded:
                        self.eta = int((self.total_bytes - downloaded) / self.current_speed)
                    else:
                        self.eta = 0

                    stats = {
                        "download_id": self.download_id,
                        "status": self.status,
                        "downloaded_bytes": downloaded,
                        "total_bytes": self.total_bytes,
                        "speed": int(self.current_speed),
                        "eta": self.eta,
                        "resumable": self.resumable,
                    }

                    segments_data = self.allocator.to_dict_list() if self.allocator else []

                if self.on_progress:
                    try:
                        self.on_progress(self.download_id, stats)
                    except Exception:
                        pass

                if self.on_segment_update:
                    try:
                        self.on_segment_update(self.download_id, segments_data)
                    except Exception:
                        pass

    def _build_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        headers.update(self.headers)
        if extra:
            headers.update(extra)
        return headers

    def _check_range_support(self) -> bool:
        """Send a test 0-0 range request to check server compliance."""
        try:
            req = urllib.request.Request(self.final_url, headers=self._build_headers({"Range": "bytes=0-0"}))
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 206
        except Exception:
            return False

    def _extract_filename_from_cd(self, cd: str) -> Optional[str]:
        """Extract filename from Content-Disposition header."""
        match = re.search(r"filename\*=UTF-8''([^;\s]+)", cd, re.IGNORECASE)
        if match:
            return urllib.parse.unquote(match.group(1))
        match = re.search(r'filename="?([^";\n]+)"?', cd, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
