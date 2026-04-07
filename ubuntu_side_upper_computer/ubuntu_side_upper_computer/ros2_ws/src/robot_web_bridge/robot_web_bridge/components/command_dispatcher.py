from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any, Callable, Iterable


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    """Result returned by the ingress admission controller.

    Args:
        accepted: Whether the command entered the dispatcher queue.
        status: Stable acknowledgement status for immediate ingress decisions.
        message: Human-readable admission outcome.
    """

    accepted: bool
    status: str
    message: str


class CommandDispatcher:
    """Bounded ingress dispatcher that isolates websocket bursts from ROS dispatch.

    The dispatcher enforces queue bounds, preserves reserved capacity for high-priority
    commands, and applies latest-only replacement for teleoperation so stale motion
    commands do not accumulate under bursty UI input.
    """

    def __init__(
        self,
        *,
        router_handle: Callable[[dict[str, Any]], None],
        ack_sender: Callable[[str, str, str], None],
        logger: Any,
        max_queue_size: int = 128,
        reserved_high_priority_slots: int = 2,
        latest_only_types: Iterable[str] = ('teleop_cmd',),
        high_priority_types: Iterable[str] = ('estop', 'resume_from_safe_stop'),
        stats_callback: Callable[[str, Any], None] | None = None,
        failure_callback: Callable[[dict[str, Any], Exception], None] | None = None,
    ) -> None:
        self._router_handle = router_handle
        self._ack_sender = ack_sender
        self._logger = logger
        self._lock = RLock()
        self._queue: deque[dict[str, Any]] = deque()
        self._max_queue_size = max(1, int(max_queue_size))
        self._reserved_high_priority_slots = max(0, min(int(reserved_high_priority_slots), self._max_queue_size - 1))
        self._latest_only_types = {str(item) for item in latest_only_types}
        self._high_priority_types = {str(item) for item in high_priority_types}
        self._stats_callback = stats_callback
        self._failure_callback = failure_callback
        self._high_watermark = 0
        self._busy_reject_count = 0
        self._latest_only_replace_count = 0
        self._preempt_count = 0
        self._processed_count = 0
        self._last_dispatch_latency_ms = 0.0
        self._last_processed_type = ''

    def enqueue(self, cmd: dict[str, Any]) -> AdmissionResult:
        """Attempt to admit one frontend command into the bounded ingress queue.

        Args:
            cmd: Canonical command envelope used by the bridge/router boundary.

        Returns:
            ``AdmissionResult`` describing whether the command was accepted.

        Raises:
            None. Queue pressure is reported through ``AdmissionResult`` so callers can
            ACK rejection synchronously without depending on exceptions.

        Boundary behavior:
            - High-priority commands may use reserved capacity and may preempt one older
              normal-priority command when the queue is completely full.
            - Latest-only commands replace an older queued command of the same type.
            - Normal commands are rejected once the non-reserved capacity is exhausted.
        """
        command_type = str(cmd.get('type', 'unknown') or 'unknown')
        with self._lock:
            cmd = dict(cmd)
            cmd['_enqueued_at_monotonic'] = monotonic()
            if command_type in self._latest_only_types:
                if self._replace_latest_only(command_type, cmd):
                    self._report('latest_only_replaced', command_type=command_type)
                    return AdmissionResult(True, 'accepted', 'latest-only command replaced stale queued entry')
            if self._can_admit(command_type):
                self._queue.append(cmd)
                self._note_depth(command_type)
                self._report('accepted', command_type=command_type)
                return AdmissionResult(True, 'accepted', 'command queued')
            if command_type in self._high_priority_types and self._preempt_one_normal_for_high_priority(cmd):
                self._note_depth(command_type)
                self._report('preempted', command_type=command_type)
                return AdmissionResult(True, 'accepted', 'high-priority command preempted normal backlog')
            self._busy_reject_count += 1
            self._report('busy_rejected', command_type=command_type)
            return AdmissionResult(False, 'rejected', 'bridge busy: ingress queue saturated')

    def process_batch(self, max_items: int) -> int:
        """Dispatch up to ``max_items`` queued commands into the command router.

        Args:
            max_items: Maximum number of queued commands to process this scheduling tick.

        Returns:
            Number of commands processed during the current invocation.

        Raises:
            None. Individual router failures are converted into immediate command ACKs.

        Boundary behavior:
            The method intentionally stops after ``max_items`` even when backlog remains,
            preserving executor time for heartbeats, readiness refreshes, and state output.
        """
        processed = 0
        limit = max(1, int(max_items))
        while processed < limit and self.process_one():
            processed += 1
        return processed

    def process_one(self) -> bool:
        """Dispatch a single queued command into the router.

        Args:
            None.

        Returns:
            ``True`` when a command was processed, else ``False`` when the queue is empty.

        Raises:
            None. Router failures are contained and mirrored as rejected ACKs.
        """
        with self._lock:
            if not self._queue:
                return False
            cmd = self._queue.popleft()
        command_type = str(cmd.get('type', 'unknown') or 'unknown')
        event_id = str(cmd.get('event_id', 'frontend-event') or 'frontend-event')
        started = monotonic()
        try:
            self._router_handle(cmd)
        except Exception as exc:
            self._logger.error(f'command dispatch failed: {command_type}: {exc}')
            self._ack_sender(event_id, 'rejected', f'command dispatch failed: {exc}')
            if self._failure_callback is not None:
                try:
                    self._failure_callback(dict(cmd), exc)
                except Exception:
                    pass
        finally:
            enqueued_at = float(cmd.get('_enqueued_at_monotonic', started) or started)
            self._last_dispatch_latency_ms = max(0.0, (started - enqueued_at) * 1000.0)
            self._last_processed_type = command_type
            self._processed_count += 1
            self._report('processed', command_type=command_type)
        return True

    def stats_snapshot(self) -> dict[str, Any]:
        """Return one immutable snapshot of dispatcher backpressure statistics.

        Args:
            None.

        Returns:
            Dictionary containing queue depth, high watermark, drop counters and the last
            observed dispatch latency.

        Raises:
            None.
        """
        with self._lock:
            depth = len(self._queue)
            return {
                'ingressQueueDepth': depth,
                'ingressQueueMax': self._max_queue_size,
                'ingressHighWatermark': self._high_watermark,
                'ingressBusyRejectCount': self._busy_reject_count,
                'teleopSupersededCount': self._latest_only_replace_count,
                'ingressPreemptCount': self._preempt_count,
                'dispatcherProcessedCount': self._processed_count,
                'dispatchLatencyMs': round(self._last_dispatch_latency_ms, 3),
                'lastDispatchedCommandType': self._last_processed_type,
            }

    def _replace_latest_only(self, command_type: str, replacement: dict[str, Any]) -> bool:
        for index in range(len(self._queue) - 1, -1, -1):
            existing = self._queue[index]
            if str(existing.get('type', '')) != command_type:
                continue
            self._queue[index] = replacement
            self._latest_only_replace_count += 1
            return True
        return False

    def _can_admit(self, command_type: str) -> bool:
        depth = len(self._queue)
        if depth < self._max_queue_size - self._reserved_high_priority_slots:
            return True
        if command_type in self._high_priority_types and depth < self._max_queue_size:
            return True
        return False

    def _preempt_one_normal_for_high_priority(self, command: dict[str, Any]) -> bool:
        for index, existing in enumerate(self._queue):
            if str(existing.get('type', '')) in self._high_priority_types:
                continue
            del self._queue[index]
            self._queue.append(command)
            self._preempt_count += 1
            return True
        return False

    def _note_depth(self, command_type: str) -> None:
        depth = len(self._queue)
        self._high_watermark = max(self._high_watermark, depth)
        self._last_processed_type = command_type

    def _report(self, kind: str, **payload: Any) -> None:
        if self._stats_callback is None:
            return
        try:
            self._stats_callback(kind, **payload)
        except TypeError:
            self._stats_callback(kind)
