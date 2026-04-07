from __future__ import annotations

import copy
import threading
from typing import Any, Callable


class SnapshotCache:
    """Thread-safe immutable snapshot cache for websocket fan-out."""

    def __init__(self, builder: Callable[[], dict[str, Any]]) -> None:
        self._builder = builder
        self._lock = threading.RLock()
        self._snapshot: dict[str, Any] = {}

    def refresh(self) -> dict[str, Any]:
        with self._lock:
            self._snapshot = self._builder()
            return copy.deepcopy(self._snapshot)

    def get(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._snapshot)
