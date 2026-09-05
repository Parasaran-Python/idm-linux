"""
Central Download Engine Orchestrator for IDM Linux
"""

import os
import threading
import time
import urllib.parse
from typing import Any, Callable, Dict, List, Optional, Union
from idm_core.category_manager import CategoryManager
from idm_core.config import Config
from idm_core.database import Database
from idm_core.queue_manager import QueueManager
from idm_core.scheduler import Scheduler
from idm_core.segment_downloader import SegmentDownloader
from idm_core.storage import StorageManager
from idm_core.stream_downloader import StreamDownloader
from idm_core.ytdlp_downloader import YTDLPDownloader


class DownloadEngine:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.config.ensure_directories()
        
        self.database = Database(self.config.database_path)
        self.database.init_db()

        self.storage = StorageManager(self.config)
        self.category_manager = CategoryManager(self.config)
        self.queue_manager = QueueManager(self.database, self)
        self.scheduler = Scheduler(self.database, self.queue_manager, self)
        self.scheduler.start()

        self.active_downloaders: Dict[str, Any] = {}
        self._listeners: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self._lock = threading.RLock()

    def register_listener(self, event_type: str, callback: Callable[[Dict[str, Any]], None]):
        """Register event listener for download_progress, download_complete, etc."""
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            self._listeners[event_type].append(callback)

    def notify(self, event_type: str, data: Dict[str, Any]):
        """Dispatch event notification to all registered listeners."""
        with self._lock:
            callbacks = list(self._listeners.get(event_type, []))
            wildcard = list(self._listeners.get("*", []))

        for cb in callbacks + wildcard:
            try:
                cb(data)
            except Exception:
                pass

    def add_download(
        self,
        url: str,
        filename: Optional[str] = None,
        save_path: Optional[str] = None,
        category: Optional[str] = None,
        connections: Optional[int] = None,
        speed_limit: int = 0,
        headers: Optional[Dict[str, str]] = None,
        queue_id: Optional[str] = None,
        total_bytes: int = 0,
        start_immediately: bool = True
    ) -> str:
        """Probe URL, categorize, register in database, and optionally start download."""
        conn_count = connections or self.config.max_connections
        headers = headers or {}
        
        # Inferred filename
        if not filename:
            path_part = urllib.parse.urlparse(url).path
            filename = os.path.basename(path_part) or "download"
            if filename.endswith(".m3u8") or filename.endswith(".mpd"):
                filename = os.path.splitext(filename)[0] + ".mp4"

        # Categorize
        if not category or category == "General":
            category = self.category_manager.get_category_for_filename(filename)

        # Destination path
        if not save_path:
            dest_dir = self.category_manager.get_destination_directory(category)
            save_path = os.path.join(dest_dir, filename)
        elif os.path.isdir(save_path):
            save_path = os.path.join(save_path, filename)

        # Avoid local collision
        save_path = os.path.join(
            os.path.dirname(save_path),
            self.storage.get_unique_filename(os.path.dirname(save_path), os.path.basename(save_path))
        )
        filename = os.path.basename(save_path)

        download_id = self.database.add_download(
            url=url,
            filename=filename,
            save_path=save_path,
            total_bytes=total_bytes,
            category=category,
            connections_count=conn_count,
            headers=headers,
            queue_id=queue_id,
            status="queued"
        )

        self.notify("download_added", {"download_id": download_id, "filename": filename, "url": url})

        if start_immediately:
            self.start_download(download_id)

        return download_id

    def start_download(self, download_id: str):
        """Start or resume a download task by ID."""
        with self._lock:
            if download_id in self.active_downloaders:
                downloader = self.active_downloaders[download_id]
                if downloader.status == "paused":
                    downloader.resume()
                return

            record = self.database.get_download(download_id)
            if not record:
                return

            url = record["url"]
            save_path = record["save_path"]
            headers = record.get("headers") or {}
            conn_count = record.get("connections_count", self.config.max_connections)
            saved_segments = self.database.get_segments(download_id)

            is_stream = url.endswith(".m3u8") or ".m3u8?" in url or url.endswith(".mpd") or ".mpd?" in url
            is_direct_media = YTDLPDownloader.is_direct_media_url(url)
            is_platform_video = not is_stream and not is_direct_media and YTDLPDownloader.is_ytdlp_available() and (
                YTDLPDownloader.is_video_platform_url(url)
                or bool(headers.get("quality"))
                or "/watch?" in url
                or "/watch/" in url
                or "/shorts/" in url
            )

            if is_platform_video:
                downloader = YTDLPDownloader(
                    download_id=download_id,
                    url=url,
                    save_path=save_path,
                    config=self.config,
                    headers=headers,
                    quality=headers.get("quality"),
                    total_bytes=record.get("total_bytes", 0),
                    on_progress=self._on_progress_callback,
                    on_complete=self._on_complete_callback,
                    on_error=self._on_error_callback,
                )
            elif is_stream:
                downloader = StreamDownloader(
                    download_id=download_id,
                    url=url,
                    save_path=save_path,
                    storage=self.storage,
                    config=self.config,
                    num_connections=conn_count,
                    headers=headers,
                    on_progress=self._on_progress_callback,
                    on_complete=self._on_complete_callback,
                    on_error=self._on_error_callback,
                )
            else:
                downloader = SegmentDownloader(
                    download_id=download_id,
                    url=url,
                    save_path=save_path,
                    storage=self.storage,
                    config=self.config,
                    num_connections=conn_count,
                    headers=headers,
                    saved_segments=saved_segments,
                    on_progress=self._on_progress_callback,
                    on_segment_update=self._on_segment_update_callback,
                    on_complete=self._on_complete_callback,
                    on_error=self._on_error_callback,
                )

            self.active_downloaders[download_id] = downloader
            self.database.update_download(download_id, status="downloading")
            downloader.start()

            self.notify("download_started", {"download_id": download_id})

    def pause_download(self, download_id: str):
        """Pause a running download."""
        with self._lock:
            if download_id in self.active_downloaders:
                downloader = self.active_downloaders[download_id]
                downloader.pause()
                self._persist_download_state(download_id, downloader)
                del self.active_downloaders[download_id]
            self.database.update_download(download_id, status="paused", speed=0)
            self.notify("download_paused", {"download_id": download_id})

    def resume_download(self, download_id: str):
        """Resume a paused download."""
        self.start_download(download_id)

    def stop_download(self, download_id: str):
        """Stop download (alias for pause)."""
        self.pause_download(download_id)

    def stop_all(self):
        """Pause all currently active downloads."""
        with self._lock:
            ids = list(self.active_downloaders.keys())
        for dl_id in ids:
            self.pause_download(dl_id)

    def delete_download(self, download_id: str, delete_files: bool = False, move_to_trash: bool = True) -> bool:
        """Remove download from queue/history and optionally delete/trash from disk."""
        with self._lock:
            if download_id in self.active_downloaders:
                downloader = self.active_downloaders[download_id]
                downloader.cancel()
                del self.active_downloaders[download_id]

            rec = self.database.get_download(download_id)
            if rec and delete_files:
                path = rec.get("save_path")
                if path and os.path.exists(path):
                    if move_to_trash:
                        self.storage.move_to_trash(path)
                    else:
                        try:
                            os.remove(path)
                        except Exception:
                            pass

            self.storage.cleanup_temp(download_id)
            deleted = self.database.delete_download(download_id)
            self.notify("download_deleted", {"download_id": download_id})
            return deleted

    def start_queue(self, queue_id: str = "main"):
        self.queue_manager.start_queue(queue_id)

    def stop_queue(self, queue_id: str = "main"):
        self.queue_manager.stop_queue(queue_id)

    def get_download_info(self, download_id: str) -> Optional[Dict[str, Any]]:
        """Get combined live stats and DB record for a download."""
        rec = self.database.get_download(download_id)
        if not rec:
            return None

        with self._lock:
            if download_id in self.active_downloaders:
                dl = self.active_downloaders[download_id]
                rec["status"] = dl.status
                rec["speed"] = int(getattr(dl, "current_speed", getattr(dl, "speed", 0)))
                rec["eta"] = getattr(dl, "eta", 0)
                rec["downloaded_bytes"] = dl.allocator.get_total_downloaded() if getattr(dl, "allocator", None) else getattr(dl, "downloaded_bytes", 0)
                rec["total_bytes"] = getattr(dl, "total_bytes", rec["total_bytes"])
                rec["segments"] = dl.allocator.to_dict_list() if getattr(dl, "allocator", None) else []
            else:
                rec["segments"] = self.database.get_segments(download_id)

        return rec

    def list_downloads(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        queue_id: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve filtered downloads list with active live statistics."""
        downloads = self.database.list_downloads(category, status, queue_id, search)
        for dl in downloads:
            dl_id = dl["id"]
            if dl_id in self.active_downloaders:
                active = self.active_downloaders[dl_id]
                dl["status"] = active.status
                dl["speed"] = int(getattr(active, "current_speed", getattr(active, "speed", 0)))
                dl["eta"] = getattr(active, "eta", 0)
                dl["downloaded_bytes"] = active.allocator.get_total_downloaded() if getattr(active, "allocator", None) else getattr(active, "downloaded_bytes", 0)
        return downloads

    def _on_progress_callback(self, download_id: str, stats: Dict[str, Any]):
        self.database.update_download(
            download_id,
            downloaded_bytes=stats.get("downloaded_bytes", 0),
            total_bytes=stats.get("total_bytes", 0),
            speed=stats.get("speed", 0),
            eta=stats.get("eta", 0),
            status=stats.get("status", "downloading")
        )
        self.notify("download_progress", stats)

    def _on_segment_update_callback(self, download_id: str, segments: List[dict]):
        self.database.save_segments(download_id, segments)
        self.notify("segment_update", {"download_id": download_id, "segments": segments})

    def _on_complete_callback(self, download_id: str, filepath: str):
        with self._lock:
            if download_id in self.active_downloaders:
                dl = self.active_downloaders[download_id]
                if getattr(dl, "status", "") in ["paused", "cancelled"]:
                    return
                del self.active_downloaders[download_id]
            else:
                rec = self.database.get_download(download_id)
                if rec and rec.get("status") in ["paused", "cancelled"]:
                    return

        file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        self.database.update_download(
            download_id,
            status="completed",
            downloaded_bytes=file_size,
            total_bytes=file_size,
            speed=0,
            eta=0,
            completed_at=time.time()
        )
        self.database.delete_segments(download_id)

        rec = self.database.get_download(download_id)
        queue_id = rec.get("queue_id") if rec else None
        self.queue_manager.on_download_completed(download_id, queue_id)

        self.notify("download_complete", {
            "download_id": download_id,
            "filepath": filepath,
            "filename": os.path.basename(filepath)
        })

    def _on_error_callback(self, download_id: str, error_msg: str):
        seg_downloader = None
        with self._lock:
            downloader = self.active_downloaders.pop(download_id, None)

            # Resilient fallback: if YTDLPDownloader failed and 0 bytes were downloaded,
            # try falling back to standard SegmentDownloader if the URL is an HTTP/HTTPS resource
            if isinstance(downloader, YTDLPDownloader):
                record = self.database.get_download(download_id)
                if (
                    record
                    and record.get("status") not in ["paused", "cancelled", "completed"]
                    and record.get("downloaded_bytes", 0) == 0
                ):
                    url = record.get("url", "")
                    if url.startswith(("http://", "https://")):
                        try:
                            conn_count = record.get("connections_count", self.config.max_connections)
                            save_path = record["save_path"]
                            saved_segments = self.database.get_segments(download_id)
                            seg_downloader = SegmentDownloader(
                                download_id=download_id,
                                url=url,
                                save_path=save_path,
                                storage=self.storage,
                                config=self.config,
                                num_connections=conn_count,
                                headers=record.get("headers") or {},
                                saved_segments=saved_segments,
                                on_progress=self._on_progress_callback,
                                on_segment_update=self._on_segment_update_callback,
                                on_complete=self._on_complete_callback,
                                on_error=self._on_error_callback,
                            )
                            self.active_downloaders[download_id] = seg_downloader
                            self.database.update_download(download_id, status="downloading", error_msg="")
                        except Exception:
                            seg_downloader = None
                            self.active_downloaders.pop(download_id, None)

        if seg_downloader:
            with self._lock:
                still_active = self.active_downloaders.get(download_id) is seg_downloader
            if still_active:
                try:
                    seg_downloader.start()
                    return
                except Exception as e:
                    with self._lock:
                        self.active_downloaders.pop(download_id, None)
                    self.database.update_download(download_id, status="error", error_msg=str(e), speed=0)
                    self.notify("download_error", {"download_id": download_id, "error": str(e)})
                    return
            return

        self.database.update_download(download_id, status="error", error_msg=error_msg, speed=0)
        self.notify("download_error", {"download_id": download_id, "error": error_msg})

    def _persist_download_state(self, download_id: str, downloader: Any):
        if getattr(downloader, "allocator", None):
            self.database.save_segments(download_id, downloader.allocator.to_dict_list())
            self.database.update_download(
                download_id,
                downloaded_bytes=downloader.allocator.get_total_downloaded(),
                total_bytes=downloader.total_bytes
            )
        else:
            dl_bytes = getattr(downloader, "downloaded_bytes", 0)
            tot_bytes = getattr(downloader, "total_bytes", 0)
            self.database.update_download(
                download_id,
                downloaded_bytes=dl_bytes,
                total_bytes=tot_bytes
            )

    def shutdown(self):
        """Cleanly terminate engine, background scheduler, and download tasks."""
        self.scheduler.stop()
        self.stop_all()
        self.database.close()
