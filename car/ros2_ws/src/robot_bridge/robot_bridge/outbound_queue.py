from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


_PRIORITY_RANK = {
    'normal': 0,
    'high': 1,
    'critical': 2,
}


@dataclass
class OutboundQueue:
    """Bounded outbound queue with latest-only replacement and priority-aware drops.

    Args:
        max_size: Maximum number of payloads retained for transport delivery.
        replaceable_types: Payload types that should collapse to the most recent value.
        high_priority_types: Payload types that should pre-empt normal traffic under congestion.
        critical_types: Payload types that must retain one reserved delivery lane when possible.
        critical_reserve_slots: Number of queue slots protected for critical traffic.

    Returns:
        None.

    Raises:
        None.

    Boundary behavior:
        Normal traffic is dropped first when the queue is saturated. High-priority payloads may
        evict the oldest normal payload. Critical payloads may evict any older non-critical
        payload and, as a last resort, the oldest critical payload so the newest safety command
        still enters the queue.
    """

    max_size: int = 64
    replaceable_types: tuple[str, ...] = ('cmd_vel', 'set_mode')
    high_priority_types: tuple[str, ...] = ('teleop_cmd', 'speak', 'start_patrol', 'track_target')
    critical_types: tuple[str, ...] = ('estop', 'stop_now', 'resume_from_safe_stop', 'set_mode', 'fault_clear')
    critical_reserve_slots: int = 1
    _items: deque[dict[str, Any]] = field(default_factory=deque)
    dropped_count: int = 0
    dropped_by_priority: dict[str, int] = field(default_factory=lambda: {'normal': 0, 'high': 0, 'critical': 0})
    dropped_by_type: dict[str, int] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self._items)

    def _priority_of(self, payload_type: str) -> str:
        if payload_type in self.critical_types:
            return 'critical'
        if payload_type in self.high_priority_types:
            return 'high'
        return 'normal'

    def _record_drop(self, payload: dict[str, Any]) -> None:
        payload_type = str(payload.get('type', '') or 'unknown')
        priority = self._priority_of(payload_type)
        self.dropped_count += 1
        self.dropped_by_priority[priority] = int(self.dropped_by_priority.get(priority, 0)) + 1
        self.dropped_by_type[payload_type] = int(self.dropped_by_type.get(payload_type, 0)) + 1

    def _remove_at(self, index: int) -> dict[str, Any]:
        payload = self._items[index]
        del self._items[index]
        return payload

    def _find_evictable_index(self, incoming_priority: str) -> int | None:
        if not self._items:
            return None
        reserve_slots = max(0, min(int(self.critical_reserve_slots), max(0, self.max_size - 1)))
        critical_count = sum(1 for item in self._items if self._priority_of(str(item.get('type', '') or '')) == 'critical')
        for priority in ('normal', 'high', 'critical'):
            if _PRIORITY_RANK[priority] > _PRIORITY_RANK[incoming_priority]:
                continue
            if priority == incoming_priority and priority == 'normal':
                continue
            for idx, item in enumerate(self._items):
                item_type = str(item.get('type', '') or '')
                item_priority = self._priority_of(item_type)
                if item_priority != priority:
                    continue
                if incoming_priority != 'critical' and item_priority == 'critical':
                    continue
                if item_priority == 'critical' and critical_count <= reserve_slots:
                    continue
                return idx
        return None

    def enqueue(self, payload: dict[str, Any]) -> None:
        payload_type = str(payload.get('type', '') or '')
        incoming_priority = self._priority_of(payload_type)
        if payload_type in self.replaceable_types:
            for idx in range(len(self._items) - 1, -1, -1):
                if str(self._items[idx].get('type', '') or '') == payload_type:
                    self._items[idx] = payload
                    return
        if len(self._items) < self.max_size:
            self._items.append(payload)
            return
        evict_index = self._find_evictable_index(incoming_priority)
        if evict_index is None:
            self._record_drop(payload)
            return
        dropped = self._remove_at(evict_index)
        self._record_drop(dropped)
        self._items.append(payload)

    def peek(self) -> dict[str, Any] | None:
        if not self._items:
            return None
        return self._items[0]

    def pop_left(self) -> dict[str, Any] | None:
        if not self._items:
            return None
        return self._items.popleft()

    def clear(self) -> None:
        self._items.clear()

    def summary(self) -> dict[str, Any]:
        priority_depth = {'normal': 0, 'high': 0, 'critical': 0}
        for item in self._items:
            priority_depth[self._priority_of(str(item.get('type', '') or ''))] += 1
        return {
            'queue_depth': len(self._items),
            'dropped_payloads': self.dropped_count,
            'priority_depth': priority_depth,
            'dropped_by_priority': dict(self.dropped_by_priority),
            'dropped_by_type': dict(self.dropped_by_type),
        }
