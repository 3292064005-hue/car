from __future__ import annotations

import time
from typing import Any

from robot_bridge.odometry import OdomState, integrate_odometry, yaw_to_quaternion
from robot_bridge.translators import payload_to_chassis, payload_to_fault, payload_to_power, payload_to_status, payload_to_voice
from robot_msgs.msg import ChassisState, Fault, PowerState, SystemStatus, VoiceCommand

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


class BridgeProjectionLayer:
    """Project accepted gateway payloads onto ROS topics and derived state."""

    def __init__(
        self,
        *,
        node: Any,
        voice_pub: Any,
        chassis_pub: Any,
        fault_pub: Any,
        status_pub: Any,
        power_pub: Any,
        odom_pub: Any,
        battery_pub: Any,
        tf_broadcaster: Any,
        odom_frame: str,
        base_frame: str,
    ) -> None:
        self._node = node
        self._voice_pub = voice_pub
        self._chassis_pub = chassis_pub
        self._fault_pub = fault_pub
        self._status_pub = status_pub
        self._power_pub = power_pub
        self._odom_pub = odom_pub
        self._battery_pub = battery_pub
        self._tf_broadcaster = tf_broadcaster
        self._odom_frame = odom_frame
        self._base_frame = base_frame
        self.odom_state = OdomState()
        self.last_odom_update = 0.0
        self.last_chassis: ChassisState | None = None
        self.last_power: PowerState | None = None
        self.last_status: SystemStatus | None = None

    def handle_payload(self, payload: dict[str, Any]) -> str:
        payload_type = str(payload.get('type', ''))
        if payload_type == 'voice_cmd':
            self._voice_pub.publish(payload_to_voice(payload))
            return payload_type
        if payload_type == 'chassis_state':
            chassis = payload_to_chassis(payload)
            self.last_chassis = chassis
            self._chassis_pub.publish(chassis)
            self.publish_odometry(chassis)
            return payload_type
        if payload_type == 'power_state':
            power = payload_to_power(payload)
            self.last_power = power
            self._power_pub.publish(power)
            self.publish_battery_state(power)
            return payload_type
        if payload_type == 'fault':
            self._fault_pub.publish(payload_to_fault(self._node, payload))
            return payload_type
        if payload_type == 'system_status':
            status = payload_to_status(payload)
            self.last_status = status
            self._status_pub.publish(status)
            return payload_type
        return payload_type

    def publish_odometry(self, chassis: ChassisState) -> None:
        now = time.monotonic()
        if self.last_odom_update == 0.0:
            self.last_odom_update = now
            return
        dt = max(0.0, now - self.last_odom_update)
        self.last_odom_update = now
        self.odom_state = integrate_odometry(
            self.odom_state,
            linear_velocity=float(chassis.linear_velocity),
            angular_velocity=float(chassis.angular_velocity),
            dt=dt,
        )
        if self._odom_pub is None or Odometry is None:
            return
        msg = Odometry()
        if hasattr(msg, 'header'):
            msg.header.stamp = self._node.get_clock().now().to_msg()
            msg.header.frame_id = self._odom_frame
        if hasattr(msg, 'child_frame_id'):
            msg.child_frame_id = self._base_frame
        if hasattr(msg, 'pose') and hasattr(msg.pose, 'pose'):
            msg.pose.pose.position.x = float(self.odom_state.x)
            msg.pose.pose.position.y = float(self.odom_state.y)
            qx, qy, qz, qw = yaw_to_quaternion(self.odom_state.yaw)
            msg.pose.pose.orientation.x = qx
            msg.pose.pose.orientation.y = qy
            msg.pose.pose.orientation.z = qz
            msg.pose.pose.orientation.w = qw
            if hasattr(msg.pose, 'covariance'):
                msg.pose.covariance[0] = 0.05
                msg.pose.covariance[7] = 0.05
                msg.pose.covariance[35] = 0.1
        if hasattr(msg, 'twist') and hasattr(msg.twist, 'twist'):
            msg.twist.twist.linear.x = float(chassis.linear_velocity)
            msg.twist.twist.angular.z = float(chassis.angular_velocity)
            if hasattr(msg.twist, 'covariance'):
                msg.twist.covariance[0] = 0.05
                msg.twist.covariance[35] = 0.1
        self._odom_pub.publish(msg)
        if self._tf_broadcaster is not None and TransformStamped is not None:
            tf_msg = TransformStamped()
            tf_msg.header.stamp = self._node.get_clock().now().to_msg()
            tf_msg.header.frame_id = self._odom_frame
            tf_msg.child_frame_id = self._base_frame
            tf_msg.transform.translation.x = float(self.odom_state.x)
            tf_msg.transform.translation.y = float(self.odom_state.y)
            qx, qy, qz, qw = yaw_to_quaternion(self.odom_state.yaw)
            tf_msg.transform.rotation.x = qx
            tf_msg.transform.rotation.y = qy
            tf_msg.transform.rotation.z = qz
            tf_msg.transform.rotation.w = qw
            self._tf_broadcaster.sendTransform(tf_msg)

    def publish_battery_state(self, power: PowerState) -> None:
        if self._battery_pub is None or BatteryState is None:
            return
        msg = BatteryState()
        if hasattr(msg, 'header'):
            msg.header.stamp = self._node.get_clock().now().to_msg()
            msg.header.frame_id = self._base_frame
        msg.voltage = float(power.battery_voltage)
        msg.percentage = max(0.0, min(1.0, float(power.battery_percent) / 100.0))
        if getattr(power, 'low_power_stop', False):
            msg.power_supply_health = getattr(BatteryState, 'POWER_SUPPLY_HEALTH_DEAD', 4)
        elif getattr(power, 'low_power_warn', False):
            msg.power_supply_health = getattr(BatteryState, 'POWER_SUPPLY_HEALTH_UNSPEC_FAILURE', 1)
        else:
            msg.power_supply_health = getattr(BatteryState, 'POWER_SUPPLY_HEALTH_GOOD', 1)
        msg.present = True
        self._battery_pub.publish(msg)
