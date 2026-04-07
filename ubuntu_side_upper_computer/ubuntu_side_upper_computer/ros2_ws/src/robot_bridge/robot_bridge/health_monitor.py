from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class LinkHealth:
    connected: bool = False
    consecutive_failures: int = 0
    rx_messages: int = 0
    tx_messages: int = 0
    ignored_messages: int = 0
    invalid_messages: int = 0
    warn_messages: int = 0
    accepted_messages: int = 0
    reconnect_count: int = 0
    queue_depth: int = 0
    dropped_payloads: int = 0
    send_failures: int = 0
    last_connected_at: float = 0.0
    last_disconnected_at: float = 0.0
    last_rx_at: float = 0.0
    last_tx_at: float = 0.0
    protocol_errors: int = 0
    last_protocol_error: str = ''
    last_disconnect_reason: str = ''
    last_payload_type: str = ''
    last_rx_type: str = ''
    last_accepted_type: str = ''

    def mark_connected(self, value: bool) -> None:
        self.connected = value
        if value:
            self.consecutive_failures = 0
            self.reconnect_count += 1
            self.last_connected_at = time.monotonic()
            self.last_disconnect_reason = ''

    def mark_disconnect(self, reason: str = '') -> None:
        self.connected = False
        self.last_disconnected_at = time.monotonic()
        if reason:
            self.last_disconnect_reason = reason

    def mark_failure(self, reason: str = '') -> None:
        self.mark_disconnect(reason)
        self.consecutive_failures += 1

    def mark_rx(self, payload_type: str = '') -> None:
        self.rx_messages += 1
        self.last_rx_at = time.monotonic()
        if payload_type:
            self.last_rx_type = payload_type

    def mark_tx(self, payload_type: str = '') -> None:
        self.tx_messages += 1
        self.last_tx_at = time.monotonic()
        if payload_type:
            self.last_payload_type = payload_type

    def mark_accept(self, payload_type: str = '') -> None:
        self.accepted_messages += 1
        if payload_type:
            self.last_accepted_type = payload_type

    def mark_ignore(self, reason: str = '') -> None:
        self.ignored_messages += 1
        if reason:
            self.last_protocol_error = reason

    def mark_warn(self, reason: str = '') -> None:
        self.warn_messages += 1
        self.protocol_errors += 1
        if reason:
            self.last_protocol_error = reason

    def mark_invalid(self, reason: str = '') -> None:
        self.invalid_messages += 1
        self.protocol_errors += 1
        if reason:
            self.last_protocol_error = reason

    def mark_send_failure(self, reason: str = '') -> None:
        self.send_failures += 1
        self.mark_failure(reason)

    def update_queue(self, *, queue_depth: int, dropped_payloads: int) -> None:
        self.queue_depth = max(0, int(queue_depth))
        self.dropped_payloads = max(0, int(dropped_payloads))

    def summary(self) -> dict[str, float | int | str | bool]:
        now = time.monotonic()
        rx_age = 0.0 if self.last_rx_at == 0.0 else round(now - self.last_rx_at, 3)
        tx_age = 0.0 if self.last_tx_at == 0.0 else round(now - self.last_tx_at, 3)
        connection_age = 0.0 if self.last_connected_at == 0.0 or not self.connected else round(now - self.last_connected_at, 3)
        disconnect_age = 0.0 if self.last_disconnected_at == 0.0 or self.connected else round(now - self.last_disconnected_at, 3)
        rate_window = max(connection_age, 1.0) if self.connected else max(disconnect_age, 1.0)
        inbound_rate_hz = round(self.rx_messages / rate_window, 3)
        outbound_rate_hz = round(self.tx_messages / rate_window, 3)
        if not self.connected:
            state = 'disconnected'
        elif self.protocol_errors > 0 or self.send_failures > 0:
            state = 'degraded'
        elif rx_age > 1.5:
            state = 'stale'
        else:
            state = 'connected'
        transport_degraded = state in {'degraded', 'stale', 'disconnected'}
        return {
            'connected': self.connected,
            'state': state,
            'transport_degraded': transport_degraded,
            'consecutive_failures': self.consecutive_failures,
            'rx_messages': self.rx_messages,
            'tx_messages': self.tx_messages,
            'accepted_messages': self.accepted_messages,
            'ignored_messages': self.ignored_messages,
            'warn_messages': self.warn_messages,
            'invalid_messages': self.invalid_messages,
            'protocol_errors': self.protocol_errors,
            'reconnect_count': self.reconnect_count,
            'queue_depth': self.queue_depth,
            'dropped_payloads': self.dropped_payloads,
            'send_failures': self.send_failures,
            'rx_age_sec': rx_age,
            'tx_age_sec': tx_age,
            'connection_age_sec': connection_age,
            'disconnect_age_sec': disconnect_age,
            'inbound_rate_hz': inbound_rate_hz,
            'outbound_rate_hz': outbound_rate_hz,
            'last_protocol_error': self.last_protocol_error,
            'last_disconnect_reason': self.last_disconnect_reason,
            'last_tx_type': self.last_payload_type,
            'last_rx_type': self.last_rx_type,
            'last_accepted_type': self.last_accepted_type,
        }
