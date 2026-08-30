"""
Token-Bucket Bandwidth Speed Limiter for IDM Linux
"""

import threading
import time
from typing import Optional


class SpeedLimiter:
    def __init__(self, rate_limit_bps: int = 0):
        self.rate_limit_bps = max(0, rate_limit_bps)
        self._tokens = 0.0
        self._last_time = time.time()
        self._lock = threading.Lock()

    def set_rate_limit(self, rate_limit_bps: int):
        with self._lock:
            self.rate_limit_bps = max(0, rate_limit_bps)
            self._tokens = 0.0
            self._last_time = time.time()

    def acquire(self, num_bytes: int):
        """Throttle transfer if needed to enforce rate_limit_bps."""
        if self.rate_limit_bps <= 0 or num_bytes <= 0:
            return

        with self._lock:
            now = time.time()
            elapsed = now - self._last_time
            self._last_time = now

            self._tokens += elapsed * self.rate_limit_bps
            burst_capacity = float(max(self.rate_limit_bps // 2, 32768))
            if self._tokens > burst_capacity:
                self._tokens = burst_capacity

            if self._tokens < num_bytes:
                needed = num_bytes - self._tokens
                sleep_time = needed / self.rate_limit_bps
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    self._tokens = 0.0
                    self._last_time = time.time()
            else:
                self._tokens -= num_bytes
