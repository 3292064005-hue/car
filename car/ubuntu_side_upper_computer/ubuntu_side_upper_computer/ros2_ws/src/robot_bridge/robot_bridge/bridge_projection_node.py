from __future__ import annotations

import time

import rclpy
try:  # pragma: no cover - lightweight test stubs may omit executors
    from rclpy.executors import MultiThreadedExecutor
except Exception:  # pragma: no cover
    MultiThreadedExecutor = None
from rclpy.node import Node
from std_msgs.msg import String

from robot_bridge.bridge_split_topics import INTERNAL_BRIDGE_ACCEPTED_PAYLOAD, INTERNAL_BRIDGE_PROJECTION_STATE
from robot_bridge.components.projection_layer import BridgeProjectionLayer
from robot_bridge.json_codec import decode_line
from robot_msgs.msg import ChassisState, EventLog, Fault, PowerState, SystemStatus, VoiceCommand
from robot_utils.constants import (
    FRAME_BASE_LINK,
    FRAME_ODOM,
    FAULT_LEVEL_ERROR,
    TOPIC_BATTERY,
    TOPIC_CHASSIS_STATE,
    TOPIC_FAULT,
    TOPIC_ODOM,
    TOPIC_POWER_STATE,
    TOPIC_SYSTEM_STATUS,
)
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.helpers import safe_json_dumps
from robot_utils.qos_profiles import qos_for
from robot_utils.error_policy import build_policy_outcome, publish_policy_outcome

try:  # pragma: no cover
    from nav_msgs.msg import Odometry
except Exception:  # pragma: no cover
    Odometry = None

try:  # pragma: no cover
    from sensor_msgs.msg import BatteryState
except Exception:  # pragma: no cover
    BatteryState = None

try:  # pragma: no cover
    from geometry_msgs.msg import TransformStamped
    from tf2_ros import TransformBroadcaster
except Exception:  # pragma: no cover
    TransformStamped = None
    TransformBroadcaster = None


class BridgeProjectionNode(Node):
    """Project accepted bridge payloads onto ROS topics in split topology."""

    def __init__(self) -> None:
        super().__init__('robot_bridge_projection')
        self.declare_parameter('publish_odom', True)
        self.callback_groups = build_callback_groups()
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('publish_battery_state', True)
        self.declare_parameter('odom_frame', FRAME_ODOM)
        self.declare_parameter('base_frame', FRAME_BASE_LINK)

        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self.voice_raw_pub = self.create_publisher(VoiceCommand, '/robot/voice/raw_cmd', qos_for('perception'))
        self.chassis_pub = self.create_publisher(ChassisState, TOPIC_CHASSIS_STATE, qos_for('telemetry'))
        self.fault_pub = self.create_publisher(Fault, TOPIC_FAULT, qos_for('fault_event'))
        self.status_pub = self.create_publisher(SystemStatus, TOPIC_SYSTEM_STATUS, qos_for('telemetry'))
        self.power_pub = self.create_publisher(PowerState, TOPIC_POWER_STATE, qos_for('telemetry'))
        self.odom_pub = self.create_publisher(Odometry, TOPIC_ODOM, qos_for('telemetry')) if Odometry is not None and bool(self.get_parameter('publish_odom').value) else None
        self.battery_pub = self.create_publisher(BatteryState, TOPIC_BATTERY, qos_for('telemetry')) if BatteryState is not None and bool(self.get_parameter('publish_battery_state').value) else None
        self.tf_broadcaster = TransformBroadcaster(self) if TransformBroadcaster is not None and TransformStamped is not None and bool(self.get_parameter('publish_tf').value) else None
        self.projection_state_pub = self.create_publisher(String, INTERNAL_BRIDGE_PROJECTION_STATE, qos_for('status_summary'))

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
        call_with_callback_group(self.create_subscription, String, INTERNAL_BRIDGE_ACCEPTED_PAYLOAD, self.on_payload, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_timer, 0.50, self.publish_projection_state, callback_group=self.callback_groups.background)

    def on_payload(self, msg: String) -> None:
        payload = decode_line(str(msg.data or ''))
        if payload is None:
            publish_policy_outcome(
                self,
                outcome=build_policy_outcome(
                    code='BRIDGE_PROJECTION_INVALID',
                    source='bridge.projection',
                    disposition='ignore_with_metric',
                    operator_message='invalid accepted payload',
                    event_name='projection_invalid',
                    event_level='warn',
                    recoverable=True,
                    evidence_reference='projection_decode',
                ),
                event_pub=self.event_pub,
            )
            return
        try:
            self.projection.handle_payload(payload)
        except Exception as exc:
            publish_policy_outcome(
                self,
                outcome=build_policy_outcome(
                    code='BRIDGE_PROJECTION_RUNTIME',
                    source='bridge.projection',
                    disposition='degraded',
                    operator_message='projection runtime error',
                    event_name='projection_runtime',
                    event_level='error',
                    recoverable=True,
                    fault_level=FAULT_LEVEL_ERROR,
                    evidence_reference='projection_layer',
                    exception=exc,
                ),
                event_pub=self.event_pub,
                fault_pub=self.fault_pub,
                fault_source='bridge_projection',
            )

    def publish_projection_state(self) -> None:
        payload: dict[str, object] = {
            'odom': {
                'x': round(self.projection.odom_state.x, 4),
                'y': round(self.projection.odom_state.y, 4),
                'yaw': round(self.projection.odom_state.yaw, 4),
            },
            'published_at': time.time(),
        }
        if self.projection.last_power is not None:
            payload.update({
                'battery_voltage': round(float(self.projection.last_power.battery_voltage), 3),
                'battery_percent': round(float(self.projection.last_power.battery_percent), 1),
                'low_power_warn': bool(getattr(self.projection.last_power, 'low_power_warn', False)),
                'low_power_stop': bool(getattr(self.projection.last_power, 'low_power_stop', False)),
            })
        if self.projection.last_status is not None:
            payload.update({
                'wifi_ok': bool(self.projection.last_status.wifi_ok),
                'camera_ok': bool(self.projection.last_status.camera_ok),
                'audio_ok': bool(self.projection.last_status.audio_ok),
                'uart_ok': bool(self.projection.last_status.uart_ok),
            })
        if self.projection.last_chassis is not None:
            payload.update({
                'control_source': self.projection.last_chassis.control_source,
                'estop': bool(self.projection.last_chassis.estop),
                'heartbeat_ok': bool(self.projection.last_chassis.heartbeat_ok),
            })
        msg = String(); msg.data = safe_json_dumps(payload)
        self.projection_state_pub.publish(msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = BridgeProjectionNode()
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
