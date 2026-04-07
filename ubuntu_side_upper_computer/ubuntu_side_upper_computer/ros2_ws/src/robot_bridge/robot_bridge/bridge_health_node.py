from __future__ import annotations

from typing import Any

import rclpy
try:  # pragma: no cover - lightweight test stubs may omit executors
    from rclpy.executors import MultiThreadedExecutor
except Exception:  # pragma: no cover
    MultiThreadedExecutor = None
from rclpy.node import Node
from std_msgs.msg import String

from robot_bridge.bridge_split_topics import (
    INTERNAL_BRIDGE_PROJECTION_STATE,
    INTERNAL_BRIDGE_PROTOCOL_STATE,
    INTERNAL_BRIDGE_TRANSPORT_STATE,
)
from robot_bridge.json_codec import decode_line
from robot_msgs.msg import EventLog, ModeState
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.constants import TOPIC_BRIDGE_SUMMARY, TOPIC_TRANSPORT_STATS
from robot_utils.helpers import safe_json_dumps
from robot_utils.qos_profiles import qos_for
from robot_utils.error_policy import build_policy_outcome, publish_policy_outcome


class BridgeHealthNode(Node):
    """Aggregate split bridge state into the legacy summary topics."""

    def __init__(self) -> None:
        super().__init__('robot_bridge_health')
        self.callback_groups = build_callback_groups()
        self.current_mode = 'IDLE'
        self.transport_state: dict[str, Any] = {}
        self.protocol_state: dict[str, Any] = {}
        self.projection_state: dict[str, Any] = {}
        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self.summary_pub = self.create_publisher(String, TOPIC_BRIDGE_SUMMARY, qos_for('status_summary'))
        self.transport_pub = self.create_publisher(String, TOPIC_TRANSPORT_STATS, qos_for('status_summary'))
        call_with_callback_group(self.create_subscription, ModeState, '/robot/mode_state', self.on_mode_state, qos_for('mode_state'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, String, INTERNAL_BRIDGE_TRANSPORT_STATE, self.on_transport_state, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, INTERNAL_BRIDGE_PROTOCOL_STATE, self.on_protocol_state, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, INTERNAL_BRIDGE_PROJECTION_STATE, self.on_projection_state, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_timer, 0.50, self.publish_summary, callback_group=self.callback_groups.background)

    def on_mode_state(self, msg: ModeState) -> None:
        self.current_mode = str(msg.current_mode or 'IDLE')

    def _decode(self, data: str, *, source: str) -> dict[str, Any]:
        payload = decode_line(str(data or ''))
        if isinstance(payload, dict):
            return payload
        publish_policy_outcome(
            self,
            outcome=build_policy_outcome(
                code='BRIDGE_HEALTH_INVALID',
                source=source,
                disposition='ignore_with_metric',
                operator_message='invalid split bridge state payload',
                event_name='health_invalid',
                event_level='warn',
                recoverable=True,
                evidence_reference='health_decode',
            ),
            event_pub=self.event_pub,
        )
        return {}

    def on_transport_state(self, msg: String) -> None:
        self.transport_state = self._decode(msg.data, source='bridge.health.transport')

    def on_protocol_state(self, msg: String) -> None:
        self.protocol_state = self._decode(msg.data, source='bridge.health.protocol')

    def on_projection_state(self, msg: String) -> None:
        self.projection_state = self._decode(msg.data, source='bridge.health.projection')

    def publish_summary(self) -> None:
        transport = dict(self.transport_state)
        protocol = dict(self.protocol_state)
        projection = dict(self.projection_state)
        full = {
            **transport,
            **{k: v for k, v in protocol.items() if k not in {'published_at'}},
            **{k: v for k, v in projection.items() if k not in {'published_at'}},
            'current_mode': self.current_mode,
        }
        compact = {
            'state': full.get('state', 'unknown'),
            'connected': bool(full.get('connected', False)),
            'transport_degraded': bool(full.get('transport_degraded', False)),
            'reconnect_count': int(full.get('reconnect_count', 0) or 0),
            'reconnect_state': full.get('reconnect_state', 'idle'),
            'reconnect_retry_in_sec': full.get('reconnect_retry_in_sec'),
            'reconnect_backoff_sec': full.get('reconnect_backoff_sec'),
            'protocol_errors': int(full.get('protocol_errors', 0) or 0),
            'queue_depth': int(full.get('queue_depth', 0) or 0),
            'dropped_payloads': int(full.get('dropped_payloads', 0) or 0),
            'last_protocol_error': full.get('last_protocol_error'),
            'last_disconnect_reason': full.get('last_disconnect_reason'),
            'rx_age_sec': full.get('rx_age_sec'),
            'tx_age_sec': full.get('tx_age_sec'),
            'heartbeat_age_sec': full.get('heartbeat_age_sec'),
            'last_rtt_ms': full.get('last_rtt_ms'),
            'stale_link': bool(full.get('stale_link', False)),
            'inbound_rate_hz': full.get('inbound_rate_hz'),
            'outbound_rate_hz': full.get('outbound_rate_hz'),
            'current_mode': self.current_mode,
            'host': full.get('host'),
            'port': full.get('port'),
            'odom': full.get('odom', {'x': 0.0, 'y': 0.0, 'yaw': 0.0}),
        }
        for key in ('battery_voltage', 'battery_percent', 'low_power_warn', 'low_power_stop', 'wifi_ok', 'camera_ok', 'audio_ok', 'uart_ok', 'control_source', 'estop', 'heartbeat_ok'):
            if key in full:
                compact[key] = full[key]
        compact_msg = String(); compact_msg.data = safe_json_dumps(compact)
        full_msg = String(); full_msg.data = safe_json_dumps(full)
        self.summary_pub.publish(compact_msg)
        self.transport_pub.publish(full_msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = BridgeHealthNode()
    try:
        if MultiThreadedExecutor is None:
            rclpy.spin(node)
        else:
            executor = MultiThreadedExecutor(num_threads=2)
            executor.add_node(node)
            executor.spin()
            executor.shutdown()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
