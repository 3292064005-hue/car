from __future__ import annotations

import time


class SimpleRateLimiter:
    def __init__(self, min_interval_sec: float) -> None:
        self.min_interval_sec = min_interval_sec
        self._last_time = 0.0

    def allow(self) -> bool:
        now = time.monotonic()
        if (now - self._last_time) >= self.min_interval_sec:
            self._last_time = now
            return True
        return False
