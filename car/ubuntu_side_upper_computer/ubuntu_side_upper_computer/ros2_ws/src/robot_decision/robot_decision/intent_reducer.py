from __future__ import annotations

"""Reducer runtime used by :mod:`robot_decision.decision_node`."""

from collections import deque
from dataclasses import dataclass, field
import threading
from typing import Callable


@dataclass
class DecisionIntent:
    """Reducer intent envelope for serialized decision-state transitions."""

    kind: str
    payload: object = None
    wait: bool = False
    result_ready: threading.Event = field(default_factory=threading.Event)
    result: object = None
    error: Exception | None = None


class DecisionIntentReducer:
    """Serialize externally triggered decision intents behind one mutation lane."""

    def __init__(
        self,
        *,
        queue_max: int,
        batch_max: int,
        sync_timeout_sec: float,
        resolve_intent: Callable[[str, object], object],
        publish_issue: Callable[[str, str, str], None],
        coalesce_kinds: set[str] | None = None,
    ) -> None:
        self._resolve_intent = resolve_intent
        self._publish_issue = publish_issue
        self._queue: deque[DecisionIntent] = deque()
        self._queue_lock = threading.RLock()
        self._drain_lock = threading.Lock()
        self._coalesced: dict[str, DecisionIntent] = {}
        self._queue_max = max(1, int(queue_max))
        self._batch_max = max(1, int(batch_max))
        self._sync_timeout_sec = max(0.01, float(sync_timeout_sec))
        self._shutdown = False
        self._coalesce_kinds = set(coalesce_kinds or {'target', 'chassis_state', 'system_status', 'runtime_params', 'tick_tasks'})

    @property
    def enabled(self) -> bool:
        return not self._shutdown

    def is_coalescable(self, kind: str) -> bool:
        return kind in self._coalesce_kinds

    def shutdown(self) -> None:
        with self._queue_lock:
            self._shutdown = True

    def submit_async(self, kind: str, payload: object = None) -> bool:
        intent = DecisionIntent(kind=kind, payload=payload, wait=False)
        with self._queue_lock:
            if self._shutdown:
                self._publish_issue('intent_rejected', f'{kind}:reducer_shutdown', 'warn')
                return False
            if self.is_coalescable(kind):
                existing = self._coalesced.get(kind)
                if existing is not None and not existing.result_ready.is_set():
                    existing.payload = payload
                    return True
            if len(self._queue) >= self._queue_max:
                self._publish_issue('intent_queue_full', f'{kind}:queue_full', 'warn')
                return False
            self._queue.append(intent)
            if self.is_coalescable(kind):
                self._coalesced[kind] = intent
        return True

    def submit_sync(self, kind: str, payload: object = None) -> object:
        intent = DecisionIntent(kind=kind, payload=payload, wait=True)
        with self._queue_lock:
            if self._shutdown:
                raise RuntimeError('decision reducer is shutting down')
            if len(self._queue) >= self._queue_max:
                raise RuntimeError('decision intent queue full')
            self._queue.append(intent)
        self.drain_batch(max_items=1)
        if not intent.result_ready.wait(timeout=self._sync_timeout_sec):
            self.drain_batch(max_items=self._batch_max)
            if not intent.result_ready.wait(timeout=self._sync_timeout_sec):
                raise TimeoutError(f'decision intent timed out: {kind}')
        if intent.error is not None:
            raise intent.error
        return intent.result

    def process(self) -> int:
        return self.drain_batch(max_items=self._batch_max)

    def drain_batch(self, *, max_items: int) -> int:
        if max_items <= 0:
            return 0
        if not self._drain_lock.acquire(blocking=False):
            return 0
        processed = 0
        try:
            while processed < max_items:
                with self._queue_lock:
                    if not self._queue:
                        break
                    intent = self._queue.popleft()
                    if self._coalesced.get(intent.kind) is intent:
                        self._coalesced.pop(intent.kind, None)
                try:
                    intent.result = self._resolve_intent(intent.kind, intent.payload)
                except Exception as exc:
                    intent.error = exc
                    if not intent.wait:
                        self._publish_issue('intent_error', f'{intent.kind}:{exc}', 'error')
                finally:
                    intent.result_ready.set()
                processed += 1
        finally:
            self._drain_lock.release()
        return processed
