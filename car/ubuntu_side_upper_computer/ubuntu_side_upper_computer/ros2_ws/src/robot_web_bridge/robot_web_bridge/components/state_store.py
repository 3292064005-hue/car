from __future__ import annotations

"""State-write façade for the websocket bridge runtime.

The bridge historically mutated ``WebBridgeState`` directly across ingress,
projection, and diagnostics code paths. This module centralizes state writes so
runtime components share one mutation boundary and one snapshot-refresh policy.
"""

from collections.abc import Callable, Mapping
from typing import Any


class StateStore:
    """Single write boundary over :class:`robot_web_bridge.state_model.WebBridgeState`.

    Args:
        state: Mutable websocket bridge state model.
        snapshot_sync: Callback used after each state mutation.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self, *, state: Any, snapshot_sync: Callable[[], None]) -> None:
        self._state = state
        self._snapshot_sync = snapshot_sync

    @property
    def state(self) -> Any:
        return self._state

    def set_attr(self, name: str, value: Any) -> None:
        """Set one scalar state attribute and refresh the snapshot cache."""
        setattr(self._state, name, value)
        self._snapshot_sync()

    def update_mapping(self, name: str, values: Mapping[str, Any]) -> None:
        """Update one mapping-backed section and refresh the snapshot cache."""
        section = getattr(self._state, name)
        section.update(dict(values))
        self._snapshot_sync()

    def replace_mapping(self, name: str, values: Mapping[str, Any]) -> None:
        """Replace one mapping-backed section and refresh the snapshot cache."""
        setattr(self._state, name, dict(values))
        self._snapshot_sync()

    def append_left(self, name: str, item: Any) -> None:
        """Push one item into a deque-backed section and refresh the snapshot cache."""
        queue = getattr(self._state, name)
        queue.appendleft(item)
        self._snapshot_sync()

    def record_trace_id(self, trace_id: str) -> None:
        """Persist the last seen correlation identifier when provided."""
        if not trace_id:
            return
        self._state.last_trace_id = trace_id
        self._snapshot_sync()

    def mutate(self, callback: Callable[[Any], None]) -> None:
        """Run one custom mutation callback and refresh the snapshot cache."""
        callback(self._state)
        self._snapshot_sync()
