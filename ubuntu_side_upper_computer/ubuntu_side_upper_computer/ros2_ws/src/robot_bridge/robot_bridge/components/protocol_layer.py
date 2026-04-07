from __future__ import annotations

from typing import Any, Callable

from robot_bridge.json_codec import decode_line
from robot_bridge.protocol_policy import classify_payload
from robot_bridge.health_monitor import LinkHealth


class BridgeProtocolLayer:
    """Validate inbound JSON payloads before projection.

    The bridge node supplies callbacks for accepted payloads, warnings and
    protocol faults so that transport/protocol/projection failure domains remain
    separated.
    """

    def __init__(
        self,
        *,
        health: LinkHealth,
        logger: Any,
        protocol_fault_threshold: int,
        on_payload: Callable[[dict[str, Any]], None],
        on_warn: Callable[[str], None],
        on_fault: Callable[[str], None],
    ) -> None:
        self._health = health
        self._logger = logger
        self._protocol_fault_threshold = max(1, int(protocol_fault_threshold))
        self._on_payload = on_payload
        self._on_warn = on_warn
        self._on_fault = on_fault

    def process_line(self, line: str) -> None:
        payload = decode_line(line)
        if payload is None:
            self._health.mark_invalid('invalid_json')
            self._logger.warn(f'invalid json from gateway: {line!r}')
            return
        payload_type = str(payload.get('type', ''))
        decision = classify_payload(payload)
        if decision.action == 'fault':
            self._health.mark_invalid(decision.reason)
            self._on_fault(decision.reason)
            return
        if decision.action == 'warn':
            self._health.mark_warn(decision.reason)
            self._on_warn(decision.reason)
            if self._health.protocol_errors >= self._protocol_fault_threshold:
                self._on_fault(decision.reason)
            return
        if decision.action == 'ignore':
            self._health.mark_ignore(decision.reason)
            self._health.mark_rx(payload_type)
            self._on_payload(payload)
            return
        self._health.mark_accept(payload_type)
        self._health.mark_rx(payload_type)
        self._on_payload(payload)
