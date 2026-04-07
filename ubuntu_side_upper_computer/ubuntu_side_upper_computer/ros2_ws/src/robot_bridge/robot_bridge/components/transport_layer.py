from __future__ import annotations

from typing import Any, Callable, Iterable

from robot_bridge.health_monitor import LinkHealth
from robot_bridge.heartbeat import HeartbeatTracker
from robot_bridge.outbound_queue import OutboundQueue
from robot_bridge.reconnect_manager import ReconnectManager
from robot_bridge.tcp_client import TcpJsonClient
from robot_utils.constants import PROTO_VER
from robot_utils.helpers import safe_json_dumps, unix_time


class BridgeTransportLayer:
    """Own TCP transport, reconnect policy, heartbeat and outbound queue.

    This component isolates transport concerns from payload protocol handling and
    ROS projection code while preserving the legacy bridge topic/service surface.
    """

    def __init__(
        self,
        *,
        client: TcpJsonClient,
        reconnect: ReconnectManager,
        heartbeat: HeartbeatTracker,
        outbound: OutboundQueue,
        health: LinkHealth,
        logger: Any,
        next_seq: Callable[[], int],
        max_drain_provider: Callable[[], int],
    ) -> None:
        self._client = client
        self._reconnect = reconnect
        self._heartbeat = heartbeat
        self._outbound = outbound
        self._health = health
        self._logger = logger
        self._next_seq = next_seq
        self._max_drain_provider = max_drain_provider

    def is_connected(self) -> bool:
        return self._client.is_connected()

    def _mark_queue(self) -> None:
        queue_summary = self._outbound.summary()
        self._health.update_queue(
            queue_depth=int(queue_summary['queue_depth']),
            dropped_payloads=int(queue_summary['dropped_payloads']),
        )

    def disconnect(self, reason: str) -> None:
        self._client.close()
        self._health.mark_disconnect(reason)
        self._mark_queue()

    def ensure_connection(self, *, on_connected: Callable[[], None], on_link_fault: Callable[[str], None]) -> None:
        self._mark_queue()
        if self._client.is_connected():
            return
        if not self._reconnect.should_retry():
            return
        ok = self._client.connect()
        self._reconnect.mark_result(ok)
        self._health.mark_connected(ok)
        if ok:
            on_connected()
            self.flush()
            return
        self._health.mark_failure('connect_failed')
        on_link_fault('tcp link disconnected')

    def enqueue(self, payload: dict[str, Any]) -> None:
        self._outbound.enqueue(payload)
        self._mark_queue()
        if self._client.is_connected():
            self.flush()

    def recv_lines(self) -> Iterable[str]:
        return self._client.recv_lines()

    def flush(self) -> None:
        if not self._client.is_connected():
            self._mark_queue()
            return
        max_items = max(1, int(self._max_drain_provider()))
        drained = 0
        while drained < max_items and self._client.is_connected():
            payload = self._outbound.peek()
            if payload is None:
                break
            payload_type = str(payload.get('type', ''))
            encoded = safe_json_dumps(payload)
            if self._client.send_line(encoded):
                self._outbound.pop_left()
                self._health.mark_tx(payload_type)
                if payload_type == 'ping':
                    seq = int(payload.get('seq', 0)) or None
                    self._heartbeat.mark_tx(seq)
                drained += 1
                continue
            self._health.mark_send_failure('send_failed')
            self.disconnect('send_failed')
            break
        self._mark_queue()

    def send_heartbeat(
        self,
        *,
        heartbeat_timeout_sec: float,
        disconnect_on_timeout: bool,
        on_timeout_fault: Callable[[str], None],
    ) -> None:
        if self._client.is_connected():
            seq = self._next_seq()
            self.enqueue({'type': 'ping', 'proto_ver': PROTO_VER, 'seq': seq, 'timestamp': unix_time()})
        heartbeat_age = self._heartbeat.age()
        if self._client.is_connected() and heartbeat_age > float(heartbeat_timeout_sec):
            on_timeout_fault('heartbeat timeout')
            if disconnect_on_timeout:
                self.disconnect('heartbeat_timeout')
                self._reconnect.mark_result(False)

    def mark_pong(self, seq: int | None) -> None:
        self._heartbeat.mark_rx(seq)

    def heartbeat_age(self) -> float | None:
        if not self._heartbeat.last_rx:
            return None
        return self._heartbeat.age()

    def last_rtt_ms(self) -> float:
        return float(self._heartbeat.last_rtt_ms)

    def reconnect_summary(self) -> dict[str, float | str]:
        return self._reconnect.summary()
