from __future__ import annotations

import time
from typing import Any

import rclpy
try:  # pragma: no cover - lightweight test stubs may omit executors
    from rclpy.executors import MultiThreadedExecutor
except Exception:  # pragma: no cover
    MultiThreadedExecutor = None
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String

from robot_bridge.bridge_split_topics import INTERNAL_BRIDGE_INBOUND_RAW, INTERNAL_BRIDGE_TRANSPORT_STATE
from robot_bridge.command_payloads import build_cmd_vel_payload, build_mode_payload, build_speak_payload
from robot_bridge.runtime_factory import build_transport_stack, declare_transport_parameters
from robot_bridge.json_codec import decode_line
from robot_msgs.msg import EventLog, Fault, ModeState, SpeakRequest
from robot_utils.constants import FAULT_LEVEL_ERROR, FAULT_LINK, FRAME_BASE_LINK, FRAME_ODOM, TOPIC_FAULT
from robot_utils.helpers import safe_json_dumps
from robot_utils.message_factory import make_event
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.qos_profiles import qos_for
from robot_utils.error_policy import build_policy_outcome, publish_policy_outcome


class BridgeTransportNode(Node):
    """Own TCP connection, outbound queue and raw inbound publication.

    This node is the runtime embodiment of the transport layer when the bridge
    stack is launched in split topology.
    """

    def __init__(self) -> None:
        super().__init__('robot_bridge_transport')
        declare_transport_parameters(self)
        self.callback_groups = build_callback_groups()
        self.seq = 0
        self.current_mode = 'IDLE'
        self.link_fault_active = False

        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self.fault_pub = self.create_publisher(Fault, TOPIC_FAULT, qos_for('fault_event'))
        self.inbound_raw_pub = self.create_publisher(String, INTERNAL_BRIDGE_INBOUND_RAW, qos_for('telemetry'))
        self.transport_state_pub = self.create_publisher(String, INTERNAL_BRIDGE_TRANSPORT_STATE, qos_for('status_summary'))

        stack = build_transport_stack(self, next_seq=self.next_seq, logger=self.get_logger())
        self.host = stack.host
        self.port = stack.port
        self.health = stack.health
        self.speak_rate_limiter = stack.speak_rate_limiter
        self.reconnect = stack.reconnect
        self.heartbeat = stack.heartbeat
        self.transport = stack.transport

        call_with_callback_group(self.create_subscription, Twist, '/robot/cmd_vel_final', self.on_cmd_vel, qos_for('control_cmd'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, ModeState, '/robot/mode_state', self.on_mode_state, qos_for('mode_state'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, SpeakRequest, '/robot/speak_tx', self.on_speak_request, qos_for('control_cmd'), callback_group=self.callback_groups.io)

        call_with_callback_group(self.create_timer, 0.20, self.ensure_connection, callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_timer, 0.05, self.poll_socket, callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_timer, float(self.get_parameter('heartbeat_period').value), self.send_heartbeat, callback_group=self.callback_groups.background)
        call_with_callback_group(self.create_timer, 0.50, self.publish_transport_state, callback_group=self.callback_groups.background)
        self.get_logger().info(f'robot_bridge_transport connecting to {self.host}:{self.port}')

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def publish_event(self, category: str, name: str, detail: str, level: str = 'info') -> None:
        self.event_pub.publish(make_event(self, category, name, detail, level=level))

    def handle_link_fault(self, description: str) -> None:
        if not self.link_fault_active:
            publish_policy_outcome(
                self,
                outcome=build_policy_outcome(
                    code=FAULT_LINK,
                    source='bridge.transport',
                    disposition='degraded',
                    operator_message=description,
                    event_name='link_fault',
                    event_level='error',
                    recoverable=True,
                    fault_level=FAULT_LEVEL_ERROR,
                    evidence_reference='transport_layer',
                ),
                event_pub=self.event_pub,
                fault_pub=self.fault_pub,
                fault_source='bridge_transport',
            )
            self.link_fault_active = True

    def ensure_connection(self) -> None:
        self.transport.ensure_connection(
            on_connected=lambda: self.publish_event('link', 'connected', 'tcp bridge transport connected'),
            on_link_fault=self.handle_link_fault,
        )
        if self.transport.is_connected():
            self.link_fault_active = False

    def on_mode_state(self, msg: ModeState) -> None:
        self.current_mode = msg.current_mode
        payload = build_mode_payload(seq=self.next_seq(), mode=msg.current_mode, requested_by=msg.requested_by, reason=msg.reason)
        self.transport.enqueue(payload)

    def on_cmd_vel(self, msg: Twist) -> None:
        payload = build_cmd_vel_payload(seq=self.next_seq(), vx=float(msg.linear.x), wz=float(msg.angular.z), mode=self.current_mode)
        self.transport.enqueue(payload)

    def on_speak_request(self, msg: SpeakRequest) -> None:
        if not self.speak_rate_limiter.allow():
            return
        payload = build_speak_payload(seq=self.next_seq(), text_id=msg.text_id, priority=int(msg.priority), requested_by=msg.requested_by)
        self.transport.enqueue(payload)

    def send_heartbeat(self) -> None:
        self.transport.send_heartbeat(
            heartbeat_timeout_sec=float(self.get_parameter('heartbeat_timeout_sec').value),
            disconnect_on_timeout=bool(self.get_parameter('disconnect_on_heartbeat_timeout').value),
            on_timeout_fault=self.handle_link_fault,
        )

    def poll_socket(self) -> None:
        if not self.transport.is_connected():
            return
        for line in self.transport.recv_lines():
            payload = decode_line(line)
            if payload is not None and str(payload.get('type', '')) == 'pong':
                seq = payload.get('seq')
                self.transport.mark_pong(int(seq) if seq is not None else None)
            self.health.mark_rx('raw')
            msg = String()
            msg.data = line
            self.inbound_raw_pub.publish(msg)
        self.transport.flush()

    def publish_transport_state(self) -> None:
        summary = self.health.summary()
        reconnect = self.transport.reconnect_summary()
        summary.update(reconnect)
        heartbeat_age = self.transport.heartbeat_age()
        stale_link = bool(heartbeat_age is not None and heartbeat_age > float(self.get_parameter('heartbeat_timeout_sec').value))
        state = 'connected' if self.transport.is_connected() else 'disconnected'
        if stale_link and self.transport.is_connected():
            state = 'stale'
        elif reconnect.get('reconnect_state') in {'attempting', 'backoff'} and not self.transport.is_connected():
            state = 'reconnecting'
        payload = {
            **summary,
            'state': state,
            'connected': bool(self.transport.is_connected()),
            'last_rtt_ms': round(self.transport.last_rtt_ms(), 3),
            'heartbeat_age_sec': round(heartbeat_age, 3) if heartbeat_age is not None else None,
            'stale_link': stale_link,
            'current_mode': self.current_mode,
            'host': self.host,
            'port': self.port,
            'transport_degraded': bool(summary.get('transport_degraded', False) or stale_link or reconnect.get('reconnect_state') in {'attempting', 'backoff'}),
            'published_at': time.time(),
        }
        msg = String(); msg.data = safe_json_dumps(payload)
        self.transport_state_pub.publish(msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = BridgeTransportNode()
    try:
        if MultiThreadedExecutor is None:
            rclpy.spin(node)
        else:
            executor = MultiThreadedExecutor(num_threads=3)
            executor.add_node(node)
            executor.spin()
            executor.shutdown()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
