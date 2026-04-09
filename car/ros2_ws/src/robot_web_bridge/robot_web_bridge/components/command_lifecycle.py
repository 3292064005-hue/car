from __future__ import annotations

"""Command lifecycle tracking for websocket bridge ingress and execution."""

from collections import Counter
from collections.abc import Callable, Mapping
from typing import Any

from .state_store import StateStore


class CommandLifecycleTracker:
    """Track command lifecycle phases in one consistent event timeline.

    Args:
        store: State mutation façade.
        now_iso: Clock callback used for stable timestamps.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self, *, store: StateStore, now_iso: Callable[[], str]) -> None:
        self._store = store
        self._now_iso = now_iso

    def record(
        self,
        *,
        command_id: str,
        command_type: str,
        phase: str,
        status: str,
        message: str,
        trace_id: str = '',
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        """Append one lifecycle event and refresh aggregate diagnostics.

        Args:
            command_id: Source command identifier.
            command_type: Logical command type.
            phase: Stable lifecycle phase.
            status: Stable outcome or intermediate status.
            message: Human-readable summary.
            trace_id: Optional correlation identifier.
            extra: Optional extra lifecycle fields.

        Returns:
            None.

        Raises:
            None.
        """

        def _apply(state: Any) -> None:
            item: dict[str, Any] = {
                'commandId': command_id,
                'commandType': command_type,
                'phase': phase,
                'status': status,
                'message': message,
                'traceId': trace_id or None,
                'failureCode': self._classify_failure_code(status=status, message=message),
                'ts': self._now_iso(),
            }
            if extra:
                item.update(dict(extra))
            state.command_timeline.appendleft(item)
            counters = Counter(dict(state.transport_stats.get('commandLifecycleCounters', {})))
            counters[f'phase:{phase}'] += 1
            counters[f'status:{status}'] += 1
            if item['failureCode'] is not None:
                counters[f"failure:{item['failureCode']}"] += 1
            stats = dict(state.transport_stats)
            stats['commandLifecycleCounters'] = dict(counters)
            stats['lastCommandLifecycle'] = item
            state.transport_stats = stats
            if trace_id:
                state.last_trace_id = trace_id

        self._store.mutate(_apply)

    def _classify_failure_code(self, *, status: str, message: str) -> str | None:
        lowered = message.lower()
        if status not in {'rejected', 'denied', 'timeout', 'cancelled'}:
            return None
        if 'unsupported command' in lowered:
            return 'unsupported_command'
        if 'queue saturated' in lowered or 'bridge busy' in lowered:
            return 'queue_saturated'
        if 'unavailable' in lowered:
            return 'dependency_unavailable'
        if 'json' in lowered or 'invalid' in lowered or 'malformed' in lowered:
            return 'validation_error'
        if 'timeout' in lowered:
            return 'timeout'
        if 'cancel' in lowered:
            return 'cancelled'
        return 'execution_failure'
