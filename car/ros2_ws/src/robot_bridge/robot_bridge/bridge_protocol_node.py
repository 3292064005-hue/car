from __future__ import annotations

import time
from typing import Any

import rclpy
try:  # pragma: no cover - lightweight test stubs may omit executors
    from rclpy.executors import MultiThreadedExecutor
except Exception:  # pragma: no cover
    MultiThreadedExecutor = None
from rclpy.node import Node
from std_msgs.msg import String

from robot_bridge.bridge_split_topics import INTERNAL_BRIDGE_ACCEPTED_PAYLOAD, INTERNAL_BRIDGE_INBOUND_RAW, INTERNAL_BRIDGE_PROTOCOL_STATE
from robot_bridge.components.protocol_layer import BridgeProtocolLayer
from robot_bridge.health_monitor import LinkHealth
from robot_bridge.json_codec import decode_line
from robot_msgs.msg import EventLog, Fault
from robot_utils.constants import FAULT_LEVEL_ERROR, FAULT_PROTOCOL, TOPIC_FAULT
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.helpers import safe_json_dumps
from robot_utils.qos_profiles import qos_for
from robot_utils.error_policy import build_policy_outcome, publish_policy_outcome


class BridgeProtocolNode(Node):
    """Validate raw inbound JSON and publish accepted payloads for projection."""

    def __init__(self) -> None:
        super().__init__('robot_bridge_protocol')
        self.declare_parameter('protocol_fault_threshold', 3)
        self.callback_groups = build_callback_groups()
        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self.fault_pub = self.create_publisher(Fault, TOPIC_FAULT, qos_for('fault_event'))
        self.accepted_pub = self.create_publisher(String, INTERNAL_BRIDGE_ACCEPTED_PAYLOAD, qos_for('telemetry'))
        self.protocol_state_pub = self.create_publisher(String, INTERNAL_BRIDGE_PROTOCOL_STATE, qos_for('status_summary'))
        self.health = LinkHealth()
        self.last_warn: str | None = None
        self.last_fault: str | None = None
        self.last_payload_type: str | None = None
        self.protocol = BridgeProtocolLayer(
            health=self.health,
            logger=self.get_logger(),
            protocol_fault_threshold=int(self.get_parameter('protocol_fault_threshold').value),
            on_payload=self.on_payload,
            on_warn=self.on_warn,
            on_fault=self.on_fault,
        )
        call_with_callback_group(self.create_subscription, String, INTERNAL_BRIDGE_INBOUND_RAW, self.on_inbound_raw, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_timer, 0.50, self.publish_protocol_state, callback_group=self.callback_groups.background)

    def on_inbound_raw(self, msg: String) -> None:
        self.protocol.process_line(str(msg.data or ''))

    def on_warn(self, reason: str) -> None:
        self.last_warn = reason
        publish_policy_outcome(
            self,
            outcome=build_policy_outcome(
                code='BRIDGE_PROTOCOL_WARN',
                source='bridge.protocol',
                disposition='ignore_with_metric',
                operator_message=reason,
                event_name='protocol_warn',
                event_level='warn',
                recoverable=True,
                evidence_reference='protocol_layer',
            ),
            event_pub=self.event_pub,
        )

    def on_fault(self, reason: str) -> None:
        self.last_fault = reason
        publish_policy_outcome(
            self,
            outcome=build_policy_outcome(
                code=FAULT_PROTOCOL,
                source='bridge.protocol',
                disposition='fault_latched',
                operator_message=reason,
                event_name='protocol_fault',
                event_level='error',
                recoverable=True,
                fault_level=FAULT_LEVEL_ERROR,
                evidence_reference='protocol_layer',
            ),
            event_pub=self.event_pub,
            fault_pub=self.fault_pub,
            fault_source='bridge_protocol',
        )

    def on_payload(self, payload: dict[str, Any]) -> None:
        payload_type = str(payload.get('type', ''))
        self.last_payload_type = payload_type
        if payload_type == 'pong':
            return
        msg = String(); msg.data = safe_json_dumps(payload)
        self.accepted_pub.publish(msg)

    def publish_protocol_state(self) -> None:
        summary = self.health.summary()
        payload = {
            **summary,
            'protocol_errors': int(summary.get('protocol_errors', 0)),
            'last_protocol_error': self.last_fault or summary.get('last_protocol_error'),
            'last_warn': self.last_warn,
            'last_payload_type': self.last_payload_type,
            'published_at': time.time(),
        }
        msg = String(); msg.data = safe_json_dumps(payload)
        self.protocol_state_pub.publish(msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = BridgeProtocolNode()
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
