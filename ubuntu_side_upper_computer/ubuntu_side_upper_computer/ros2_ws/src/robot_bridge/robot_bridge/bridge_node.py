from __future__ import annotations

from typing import Any

import rclpy
try:
    from rclpy.executors import MultiThreadedExecutor
except Exception:  # pragma: no cover
    MultiThreadedExecutor = None
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String

from robot_bridge.command_payloads import build_cmd_vel_payload, build_mode_payload, build_speak_payload
from robot_bridge.runtime_factory import LEGACY_MONOLITH_RUNTIME_LABEL, build_transport_stack, declare_transport_parameters
from robot_bridge.components.health_layer import BridgeHealthLayer
from robot_bridge.components.projection_layer import BridgeProjectionLayer
from robot_bridge.components.protocol_layer import BridgeProtocolLayer
from robot_msgs.msg import ChassisState, EventLog, Fault, ModeState, PowerState, SpeakRequest, SystemStatus, VoiceCommand
from robot_utils.constants import (
    FAULT_LEVEL_ERROR,
    FAULT_LINK,
    FAULT_PROTOCOL,
    FRAME_BASE_LINK,
    FRAME_ODOM,
    TOPIC_BATTERY,
    TOPIC_BRIDGE_SUMMARY,
    TOPIC_CHASSIS_STATE,
    TOPIC_FAULT,
    TOPIC_ODOM,
    TOPIC_POWER_STATE,
    TOPIC_SYSTEM_STATUS,
    TOPIC_TRANSPORT_STATS,
)
from robot_utils.helpers import safe_json_dumps
from robot_utils.message_factory import make_event, make_fault
from robot_utils.qos_profiles import qos_for
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.error_policy import build_policy_outcome, publish_policy_outcome

try:  # pragma: no cover - depends on ROS desktop packages
    from nav_msgs.msg import Odometry
except Exception:  # pragma: no cover
    Odometry = None

try:  # pragma: no cover - depends on ROS desktop packages
    from sensor_msgs.msg import BatteryState
except Exception:  # pragma: no cover
    BatteryState = None

try:  # pragma: no cover - depends on ROS desktop packages
    from geometry_msgs.msg import TransformStamped
    from tf2_ros import TransformBroadcaster
except Exception:  # pragma: no cover
    TransformStamped = None
    TransformBroadcaster = None


class BridgeNode(Node):
    """TCP JSON bridge coordinator.

    The node preserves the original ROS topic/service surface while delegating
    transport, protocol validation, projection and health summarisation to
    dedicated components.
    """

    def __init__(self) -> None:
        super().__init__('robot_bridge')
        declare_transport_parameters(self)
        self.declare_parameter('protocol_fault_threshold', 3)
        self.declare_parameter('publish_odom', True)
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('publish_battery_state', True)
        self.declare_parameter('odom_frame', FRAME_ODOM)
        self.declare_parameter('base_frame', FRAME_BASE_LINK)

        self.callback_groups = build_callback_groups()
        self.seq = 0
        self.current_mode = 'IDLE'
        self.link_fault_active = False

        self.voice_raw_pub = self.create_publisher(VoiceCommand, '/robot/voice/raw_cmd', qos_for('perception'))
        self.chassis_pub = self.create_publisher(ChassisState, TOPIC_CHASSIS_STATE, qos_for('telemetry'))
        self.fault_pub = self.create_publisher(Fault, TOPIC_FAULT, qos_for('fault_event'))
        self.status_pub = self.create_publisher(SystemStatus, TOPIC_SYSTEM_STATUS, qos_for('telemetry'))
        self.power_pub = self.create_publisher(PowerState, TOPIC_POWER_STATE, qos_for('telemetry'))
        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self.summary_pub = self.create_publisher(String, TOPIC_BRIDGE_SUMMARY, qos_for('status_summary'))
        self.transport_pub = self.create_publisher(String, TOPIC_TRANSPORT_STATS, qos_for('status_summary'))
        self.odom_pub = self.create_publisher(Odometry, TOPIC_ODOM, qos_for('telemetry')) if Odometry is not None and bool(self.get_parameter('publish_odom').value) else None
        self.battery_pub = self.create_publisher(BatteryState, TOPIC_BATTERY, qos_for('telemetry')) if BatteryState is not None and bool(self.get_parameter('publish_battery_state').value) else None
        self.tf_broadcaster = TransformBroadcaster(self) if TransformBroadcaster is not None and TransformStamped is not None and bool(self.get_parameter('publish_tf').value) else None

        stack = build_transport_stack(self, next_seq=self.next_seq, logger=self.get_logger())
        self.host = stack.host
        self.port = stack.port
        self.health = stack.health
        self.speak_rate_limiter = stack.speak_rate_limiter
        self.reconnect = stack.reconnect
        self.heartbeat = stack.heartbeat
        self.transport = stack.transport
        self.projection = BridgeProjectionLayer(
            node=self,
            voice_pub=self.voice_raw_pub,
            chassis_pub=self.chassis_pub,
            fault_pub=self.fault_pub,
            status_pub=self.status_pub,
            power_pub=self.power_pub,
            odom_pub=self.odom_pub,
            battery_pub=self.battery_pub,
            tf_broadcaster=self.tf_broadcaster,
            odom_frame=str(self.get_parameter('odom_frame').value),
            base_frame=str(self.get_parameter('base_frame').value),
        )
        self.health_view = BridgeHealthLayer(
            health=self.health,
            reconnect=self.reconnect,
            heartbeat=self.heartbeat,
            projection=self.projection,
            current_mode_provider=lambda: self.current_mode,
            heartbeat_timeout_provider=lambda: float(self.get_parameter('heartbeat_timeout_sec').value),
            host=self.host,
            port=self.port,
        )
        self.protocol = BridgeProtocolLayer(
            health=self.health,
            logger=self.get_logger(),
            protocol_fault_threshold=int(self.get_parameter('protocol_fault_threshold').value),
            on_payload=self.handle_payload,
            on_warn=lambda reason: self.publish_event('bridge', 'invalid_payload', reason, level='warn'),
            on_fault=self.handle_protocol_fault,
        )

        call_with_callback_group(self.create_subscription, Twist, '/robot/cmd_vel_final', self.on_cmd_vel, qos_for('control_cmd'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, ModeState, '/robot/mode_state', self.on_mode_state, qos_for('mode_state'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, SpeakRequest, '/robot/speak_tx', self.on_speak_request, qos_for('control_cmd'), callback_group=self.callback_groups.io)

        self.link_timer = call_with_callback_group(self.create_timer, 0.20, self.ensure_connection, callback_group=self.callback_groups.io)
        self.poll_timer = call_with_callback_group(self.create_timer, 0.05, self.poll_socket, callback_group=self.callback_groups.io)
        hb_period = float(self.get_parameter('heartbeat_period').value)
        self.heartbeat_timer = call_with_callback_group(self.create_timer, hb_period, self.send_heartbeat, callback_group=self.callback_groups.background)
        self.summary_timer = call_with_callback_group(self.create_timer, 0.50, self.publish_summary, callback_group=self.callback_groups.background)
        self.get_logger().info(f'robot_bridge connecting to {self.host}:{self.port} runtime={LEGACY_MONOLITH_RUNTIME_LABEL}')

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
                fault_source='bridge',
            )
            self.link_fault_active = True

    def handle_protocol_fault(self, description: str) -> None:
        publish_policy_outcome(
            self,
            outcome=build_policy_outcome(
                code=FAULT_PROTOCOL,
                source='bridge.protocol',
                disposition='fault_latched',
                operator_message=description,
                event_name='protocol_fault',
                event_level='error',
                recoverable=True,
                fault_level=FAULT_LEVEL_ERROR,
                evidence_reference='protocol_layer',
            ),
            event_pub=self.event_pub,
            fault_pub=self.fault_pub,
            fault_source='bridge',
        )

    def ensure_connection(self) -> None:
        self.transport.ensure_connection(
            on_connected=lambda: self.publish_event('link', 'connected', 'tcp bridge connected'),
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

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def send_heartbeat(self) -> None:
        self.transport.send_heartbeat(
            heartbeat_timeout_sec=float(self.get_parameter('heartbeat_timeout_sec').value),
            disconnect_on_timeout=bool(self.get_parameter('disconnect_on_heartbeat_timeout').value),
            on_timeout_fault=self.handle_link_fault,
        )

    def poll_socket(self) -> None:
        for line in self.transport.recv_lines():
            self.protocol.process_line(line)
        self.transport.flush()

    def handle_payload(self, payload: dict[str, Any]) -> None:
        payload_type = self.projection.handle_payload(payload)
        if payload_type == 'system_status' and self.projection.last_status is not None:
            if self.projection.last_status.wifi_ok and self.projection.last_status.uart_ok:
                self.link_fault_active = False
            return
        if payload_type == 'task_state':
            self.publish_event('task', 'gateway_task_state', safe_json_dumps(payload))
            return
        if payload_type == 'pong':
            self.transport.mark_pong(int(payload.get('seq', 0)))
            self.link_fault_active = False
            return
        if payload_type in {'voice_cmd', 'chassis_state', 'power_state', 'fault'}:
            return
        self.publish_event('bridge', 'unhandled_payload', str(payload), level='warn')

    def publish_summary(self) -> None:
        transport = self.health_view.transport_snapshot()
        compact = {
            'connected': transport['connected'],
            'state': transport['state'],
            'transport_degraded': transport['transport_degraded'],
            'reconnect_count': transport['reconnect_count'],
            'reconnect_state': transport['reconnect_state'],
            'reconnect_retry_in_sec': transport['reconnect_retry_in_sec'],
            'reconnect_backoff_sec': transport['reconnect_backoff_sec'],
            'protocol_errors': transport['protocol_errors'],
            'queue_depth': transport['queue_depth'],
            'dropped_payloads': transport['dropped_payloads'],
            'last_protocol_error': transport['last_protocol_error'],
            'last_disconnect_reason': transport['last_disconnect_reason'],
            'rx_age_sec': transport['rx_age_sec'],
            'tx_age_sec': transport['tx_age_sec'],
            'heartbeat_age_sec': transport['heartbeat_age_sec'],
            'last_rtt_ms': transport['last_rtt_ms'],
            'stale_link': transport['stale_link'],
            'inbound_rate_hz': transport['inbound_rate_hz'],
            'outbound_rate_hz': transport['outbound_rate_hz'],
            'current_mode': transport['current_mode'],
            'host': transport['host'],
            'port': transport['port'],
            'odom': transport['odom'],
        }
        if 'battery_voltage' in transport:
            compact['battery_voltage'] = transport['battery_voltage']
            compact['battery_percent'] = transport['battery_percent']
            compact['low_power_warn'] = transport['low_power_warn']
            compact['low_power_stop'] = transport['low_power_stop']
        for key in ('wifi_ok', 'camera_ok', 'audio_ok', 'uart_ok', 'control_source', 'estop', 'heartbeat_ok'):
            if key in transport:
                compact[key] = transport[key]
        msg = String()
        msg.data = safe_json_dumps(compact)
        self.summary_pub.publish(msg)
        transport_msg = String()
        transport_msg.data = safe_json_dumps(transport)
        self.transport_pub.publish(transport_msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = BridgeNode()
    if MultiThreadedExecutor is None:
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()
            rclpy.shutdown()
        return
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
