"""
Scheduler for Time-Based Automated Download Queue Triggers
"""

import datetime
import os
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional
from idm_core.platform import system_power_action


class Scheduler:
    def __init__(self, database: Any, queue_manager: Any, engine: Any):
        self.database = database
        self.queue_manager = queue_manager
        self.engine = engine
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start scheduler background monitor thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop scheduler monitor thread."""
        self._stop_event.set()

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_schedules()
            except Exception:
                pass
            time.sleep(10)

    def _check_schedules(self):
        now = datetime.datetime.now()
        current_time_str = now.strftime("%H:%M")

        queues = self.database.list_queues()
        for q in queues:
            start_t = q.get("start_time")
            stop_t = q.get("stop_time")

            if start_t and start_t == current_time_str:
                self.queue_manager.start_queue(q["id"])

            if stop_t and stop_t == current_time_str:
                self.queue_manager.stop_queue(q["id"])

    def execute_post_action(self, action: str):
        """Execute post-download action (shutdown/sleep/notify)."""
        act = (action or "none").lower()
        if act == "shutdown":
            system_power_action("shutdown")
        elif act in ["sleep", "suspend"]:
            system_power_action("sleep")
        elif act == "notify":
            self.engine.notify("notification", {"title": "IDM Linux", "message": "All downloads in queue finished."})
