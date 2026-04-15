from __future__ import annotations

from typing import Any
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import BatteryState, JointState
from std_msgs.msg import String

from robot_description.description_model import load_description_model
from robot_msgs.msg import ChassisState, PowerState
from robot_utils.helpers import monotonic_time, safe_json_dumps
from robot_utils.qos_profiles import qos_for
from .hardware_adapter import WheelDriveEstimator, build_hardware_boundary_snapshot


class RobotHardwareInterfaceNode(Node):
    """Publish standard hardware-facing topics derived from robot-specific telemetry.

    This node keeps the existing business-domain topics intact while exporting a
    ROS-native compatibility surface for odometry, battery, and actuator tooling.
    """

    def __init__(self) -> None:
        super().__init__('robot_hardware_interface')
        self.declare_parameter('joint_state_topic', '/joint_states')
        self.declare_parameter('battery_state_topic', '/battery_state')
        self.declare_parameter('cmd_vel_observed_topic', '/cmd_vel')
        self.declare_parameter('summary_topic', '/robot/hardware_interface/summary')
        self.declare_parameter('description_path', '')
        self.declare_parameter('hardware_interface_config_path', '')
        self.declare_parameter('left_wheel_joint_name', 'left_wheel_joint')
        self.declare_parameter('right_wheel_joint_name', 'right_wheel_joint')
        self.declare_parameter('compatibility_surface_role', 'ros_projection_only')
        self.declare_parameter('board_validation_in_repo', False)
        self.declare_parameter('board_execution_confirmed', False)
        self.declare_parameter('feedback_source', 'external_transport_or_mock')
        self.declare_parameter('actuation_boundary', 'outside_ros_projection_node')
        self.declare_parameter('transport_authority', 'external_board_controller')
        self.declare_parameter('verification_stage', 'host_harness_only')
        self.declare_parameter('command_transport', 'tcp_json_bridge')
        self.declare_parameter('verification_artifact_path', '')

        self._last_chassis_at = monotonic_time()
        self._description_loaded = False
        self._description_robot_name = ''
        description_path = str(self.get_parameter('description_path').value or '').strip()
        if description_path:
            model = load_description_model(description_path)
            self._description_loaded = True
            self._description_robot_name = model.robot_name

        verification_artifact_path = str(self.get_parameter('verification_artifact_path').value or '').strip()
        config_path = str(self.get_parameter('hardware_interface_config_path').value or '').strip()
        if verification_artifact_path and config_path and not Path(verification_artifact_path).is_absolute():
            verification_artifact_path = str((Path(config_path).resolve().parent / verification_artifact_path).resolve())

        self._boundary_snapshot = build_hardware_boundary_snapshot(
            compatibility_surface_role=str(self.get_parameter('compatibility_surface_role').value),
            board_validation_in_repo=bool(self.get_parameter('board_validation_in_repo').value),
            board_execution_confirmed=bool(self.get_parameter('board_execution_confirmed').value),
            feedback_source=str(self.get_parameter('feedback_source').value),
            actuation_boundary=str(self.get_parameter('actuation_boundary').value),
            transport_authority=str(self.get_parameter('transport_authority').value),
            verification_stage=str(self.get_parameter('verification_stage').value),
            command_transport=str(self.get_parameter('command_transport').value),
            verification_artifact_path=verification_artifact_path,
            verification_reference_config_path=(Path(config_path).resolve().parent if config_path else None),
        )

        self._last_power: PowerState | None = None
        self._wheel_estimator = WheelDriveEstimator()
        self._latest_joint_state: JointState | None = None
        self._latest_cmd: Twist | None = None

        self.cmd_pub = self.create_publisher(Twist, str(self.get_parameter('cmd_vel_observed_topic').value), qos_for('control_cmd'))
        self.joint_pub = self.create_publisher(JointState, str(self.get_parameter('joint_state_topic').value), qos_for('telemetry'))
        self.battery_pub = self.create_publisher(BatteryState, str(self.get_parameter('battery_state_topic').value), qos_for('telemetry'))
        self.summary_pub = self.create_publisher(String, str(self.get_parameter('summary_topic').value), qos_for('status_summary'))

        self.create_subscription(Twist, '/robot/cmd_vel_final', self.on_final_cmd, qos_for('control_cmd'))
        self.create_subscription(ChassisState, '/robot/chassis_state', self.on_chassis_state, qos_for('telemetry'))
        self.create_subscription(PowerState, '/robot/power_state', self.on_power_state, qos_for('telemetry'))
        self.summary_timer = self.create_timer(0.5, self.publish_summary)

    def on_final_cmd(self, msg: Twist) -> None:
        """Mirror the final control output onto the standard ``/cmd_vel`` surface.

        Args:
            msg: Final control command selected by ``robot_control``.

        Returns:
            None.

        Raises:
            None. Publish failures are delegated to rclpy.
        """
        self._latest_cmd = msg
        self.cmd_pub.publish(msg)

    def on_chassis_state(self, msg: ChassisState) -> None:
        """Project wheel RPM feedback into ``sensor_msgs/JointState``.

        Args:
            msg: Domain-specific chassis telemetry.

        Returns:
            None.

        Raises:
            None. Invalid timing collapses to a non-negative interval.
        """
        now = monotonic_time()
        dt_sec = max(0.0, now - self._last_chassis_at)
        self._last_chassis_at = now
        snapshot = self._wheel_estimator.update(left_rpm=float(msg.left_rpm), right_rpm=float(msg.right_rpm), dt_sec=dt_sec)
        joint = JointState()
        stamp = self.get_clock().now().to_msg()
        joint.header.stamp = stamp
        joint.name = [
            str(self.get_parameter('left_wheel_joint_name').value),
            str(self.get_parameter('right_wheel_joint_name').value),
        ]
        joint.position = [snapshot.left_position_rad, snapshot.right_position_rad]
        joint.velocity = [snapshot.left_velocity_rad_s, snapshot.right_velocity_rad_s]
        self._latest_joint_state = joint
        self.joint_pub.publish(joint)

    def on_power_state(self, msg: PowerState) -> None:
        """Translate battery telemetry into ``sensor_msgs/BatteryState``.

        Args:
            msg: Domain-specific power telemetry.

        Returns:
            None.

        Raises:
            None.
        """
        self._last_power = msg
        battery = BatteryState()
        battery.header.stamp = self.get_clock().now().to_msg()
        battery.voltage = float(msg.battery_voltage)
        battery.percentage = max(0.0, min(1.0, float(msg.battery_percent) / 100.0))
        battery.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        battery.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_GOOD
        self.battery_pub.publish(battery)

    def publish_summary(self) -> None:
        """Publish a lightweight JSON summary for dashboards and release evidence.

        Returns:
            None.

        Raises:
            None.
        """
        boundary = self._boundary_snapshot.to_dict()
        payload: dict[str, Any] = {
            'jointStateAvailable': self._latest_joint_state is not None,
            'batteryStateAvailable': self._last_power is not None,
            'cmdObserved': self._latest_cmd is not None,
            'descriptionLoaded': self._description_loaded,
            'robotName': self._description_robot_name,
            'boundary': boundary,
            'transportAuthority': boundary['transportAuthority'],
            'verificationStage': boundary['verificationStage'],
            'executionEvidenceClass': boundary['executionEvidenceClass'],
            'claimScope': boundary['claimScope'],
        }
        if self._last_power is not None:
            payload['batteryPercent'] = float(self._last_power.battery_percent)
            payload['batteryVoltage'] = float(self._last_power.battery_voltage)
        msg = String()
        msg.data = safe_json_dumps(payload)
        self.summary_pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = RobotHardwareInterfaceNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
