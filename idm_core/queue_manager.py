"""
Queue Manager for Sequential and Concurrent Download Queue Processing
"""

import threading
import time
from typing import Any, Dict, List, Optional, Set


class QueueManager:
    def __init__(self, database: Any, engine: Any):
        self.database = database
        self.engine = engine
        self._active_queues: Set[str] = set()
        self._lock = threading.RLock()

    def start_queue(self, queue_id: str):
        """Activate a download queue and dispatch initial batch."""
        with self._lock:
            self._active_queues.add(queue_id)
            self._process_queue(queue_id)

    def stop_queue(self, queue_id: str):
        """Deactivate a queue and pause its running tasks."""
        with self._lock:
            if queue_id in self._active_queues:
                self._active_queues.remove(queue_id)

            downloads = self.database.list_downloads(queue_id=queue_id)
            for dl in downloads:
                if dl["status"] == "downloading":
                    self.engine.pause_download(dl["id"])

    def on_download_completed(self, download_id: str, queue_id: Optional[str]):
        """Handler called when a download finishes to progress the queue."""
        if not queue_id:
            return
        with self._lock:
            if queue_id in self._active_queues:
                self._process_queue(queue_id)

    def _process_queue(self, queue_id: str):
        """Check queue limits and start next pending download."""
        if queue_id not in self._active_queues:
            return

        queues = self.database.list_queues()
        q_info = next((q for q in queues if q["id"] == queue_id), None)
        max_concurrent = q_info.get("max_concurrent", 1) if q_info else 1

        downloads = self.database.list_downloads(queue_id=queue_id)
        active_count = sum(1 for d in downloads if d["status"] == "downloading")
        slots_available = max_concurrent - active_count

        if slots_available > 0:
            pending = [d for d in downloads if d["status"] in ["queued", "paused"]]
            for d in pending[:slots_available]:
                self.engine.start_download(d["id"])

        # If no pending and no active, queue finished
        if active_count == 0 and not any(d["status"] in ["queued", "paused"] for d in downloads):
            self.stop_queue(queue_id)
            self.engine.notify("queue_finished", {"queue_id": queue_id})

    def get_queue_state(self, queue_id: str) -> Dict[str, Any]:
        with self._lock:
            is_active = queue_id in self._active_queues
            downloads = self.database.list_downloads(queue_id=queue_id)
            return {
                "queue_id": queue_id,
                "is_active": is_active,
                "total_items": len(downloads),
                "active_items": sum(1 for d in downloads if d["status"] == "downloading"),
                "completed_items": sum(1 for d in downloads if d["status"] == "completed"),
            }
