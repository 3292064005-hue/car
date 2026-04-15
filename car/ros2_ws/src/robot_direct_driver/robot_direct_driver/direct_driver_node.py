from __future__ import annotations

from pathlib import Path
from typing import Any
import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import BatteryState, JointState
from std_msgs.msg import String

from robot_description.description_model import load_description_model
from robot_hardware_interface.hardware_adapter import WheelDriveEstimator, build_hardware_boundary_snapshot
from robot_msgs.msg import ChassisState, PowerState, SystemStatus
from robot_utils.helpers import monotonic_time, safe_json_dumps
from robot_utils.qos_profiles import qos_for


class DirectDriverNode(Node):
    """Dedicated direct-driver lane hosted in its own package.

    The node owns command projection, wheel-state integration, battery/runtime
    supervision, and bridge-summary publication inside a separate package. This
    keeps the direct-driver lane distinct from the projection-only hardware
    interface while preserving the existing ROS topic surface consumed by the
    rest of the system.
    """

    def __init__(self) -> None:
        super().__init__('robot_direct_driver')
        self.declare_parameter('joint_state_topic', '/joint_states')
        self.declare_parameter('battery_state_topic', '/battery_state')
        self.declare_parameter('cmd_vel_observed_topic', '/cmd_vel')
        self.declare_parameter('summary_topic', '/robot/hardware_interface/summary')
        self.declare_parameter('bridge_summary_topic', '/robot/bridge/summary')
        self.declare_parameter('chassis_state_topic', '/robot/chassis_state')
        self.declare_parameter('power_state_topic', '/robot/power_state')
        self.declare_parameter('system_status_topic', '/robot/system_status')
        self.declare_parameter('description_path', '')
        self.declare_parameter('hardware_interface_config_path', '')
        self.declare_parameter('left_wheel_joint_name', 'left_wheel_joint')
        self.declare_parameter('right_wheel_joint_name', 'right_wheel_joint')
        self.declare_parameter('compatibility_surface_role', 'direct_driver')
        self.declare_parameter('board_validation_in_repo', False)
        self.declare_parameter('board_execution_confirmed', False)
        self.declare_parameter('feedback_source', 'direct_board_feedback')
        self.declare_parameter('actuation_boundary', 'inside_ros_driver')
        self.declare_parameter('transport_authority', 'ros_process_driver')
        self.declare_parameter('verification_stage', 'host_harness_only')
        self.declare_parameter('command_transport', 'direct_driver_loop')
        self.declare_parameter('verification_artifact_path', '')
        self.declare_parameter('direct_driver_lane_policy', 'separate_package_required')
        self.declare_parameter('driver_update_rate_hz', 20.0)
        self.declare_parameter('summary_rate_hz', 2.0)
        self.declare_parameter('command_timeout_sec', 1.0)
        self.declare_parameter('wheel_radius_m', 0.033)
        self.declare_parameter('track_width_m', 0.18)
        self.declare_parameter('battery_nominal_voltage', 12.6)
        self.declare_parameter('battery_empty_voltage', 10.8)
        self.declare_parameter('battery_drain_per_meter', 0.015)
        self.declare_parameter('battery_drain_idle_per_min', 0.03)
        self.declare_parameter('status_wifi_ok', True)
        self.declare_parameter('status_camera_ok', True)
        self.declare_parameter('status_audio_ok', True)
        self.declare_parameter('status_uart_ok', True)

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
            direct_driver_lane_policy=str(self.get_parameter('direct_driver_lane_policy').value),
        )

        self._wheel_estimator = WheelDriveEstimator()
        self._latest_joint_state: JointState | None = None
        self._latest_cmd: Twist = Twist()
        self._last_cmd_at: float = monotonic_time()
        self._last_update_at: float = monotonic_time()
        self._battery_percent: float = 100.0
        self._battery_voltage: float = float(self.get_parameter('battery_nominal_voltage').value)
        self._last_power: PowerState | None = None

        self.cmd_pub = self.create_publisher(Twist, str(self.get_parameter('cmd_vel_observed_topic').value), qos_for('control_cmd'))
        self.joint_pub = self.create_publisher(JointState, str(self.get_parameter('joint_state_topic').value), qos_for('telemetry'))
        self.battery_pub = self.create_publisher(BatteryState, str(self.get_parameter('battery_state_topic').value), qos_for('telemetry'))
        self.summary_pub = self.create_publisher(String, str(self.get_parameter('summary_topic').value), qos_for('status_summary'))
        self.bridge_summary_pub = self.create_publisher(String, str(self.get_parameter('bridge_summary_topic').value), qos_for('status_summary'))
        self.chassis_pub = self.create_publisher(ChassisState, str(self.get_parameter('chassis_state_topic').value), qos_for('telemetry'))
        self.power_pub = self.create_publisher(PowerState, str(self.get_parameter('power_state_topic').value), qos_for('telemetry'))
        self.system_pub = self.create_publisher(SystemStatus, str(self.get_parameter('system_status_topic').value), qos_for('telemetry'))

        self.create_subscription(Twist, '/robot/cmd_vel_final', self.on_final_cmd, qos_for('control_cmd'))
        self.driver_timer = self.create_timer(1.0 / float(self.get_parameter('driver_update_rate_hz').value), self.driver_step)
        self.summary_timer = self.create_timer(1.0 / float(self.get_parameter('summary_rate_hz').value), self.publish_summary)

    def on_final_cmd(self, msg: Twist) -> None:
        """Accept the final control command for the direct-driver lane.

        Args:
            msg: Arbitration result from ``robot_control``.

        Returns:
            None.

        Raises:
            None.
        """
        self._latest_cmd = msg
        self._last_cmd_at = monotonic_time()
        self.cmd_pub.publish(msg)

    def _command_stale(self, *, now: float) -> bool:
        timeout_sec = float(self.get_parameter('command_timeout_sec').value)
        return timeout_sec > 0.0 and (now - self._last_cmd_at) > timeout_sec

    def _compute_wheel_rpm(self, linear_x: float, angular_z: float) -> tuple[float, float]:
        wheel_radius = max(float(self.get_parameter('wheel_radius_m').value), 1e-6)
        track_width = max(float(self.get_parameter('track_width_m').value), 1e-6)
        left_linear = linear_x - angular_z * track_width * 0.5
        right_linear = linear_x + angular_z * track_width * 0.5
        left_rpm = (left_linear / wheel_radius) * (60.0 / (2.0 * math.pi))
        right_rpm = (right_linear / wheel_radius) * (60.0 / (2.0 * math.pi))
        return left_rpm, right_rpm

    def _update_battery(self, *, linear_x: float, now: float) -> None:
        dt_sec = max(0.0, now - self._last_update_at)
        distance_m = abs(linear_x) * dt_sec
        active_drain = distance_m * float(self.get_parameter('battery_drain_per_meter').value)
        idle_drain = (dt_sec / 60.0) * float(self.get_parameter('battery_drain_idle_per_min').value)
        self._battery_percent = max(0.0, min(100.0, self._battery_percent - active_drain - idle_drain))
        nominal = float(self.get_parameter('battery_nominal_voltage').value)
        empty = float(self.get_parameter('battery_empty_voltage').value)
        ratio = self._battery_percent / 100.0
        self._battery_voltage = empty + (nominal - empty) * ratio

    def driver_step(self) -> None:
        """Run one driver-lane projection step.

        Returns:
            None.

        Raises:
            None. Invalid timing collapses to safe zero-command output.
        """
        now = monotonic_time()
        dt_sec = max(0.0, now - self._last_update_at)
        stale = self._command_stale(now=now)
        command = Twist()
        if not stale:
            command = self._latest_cmd
        linear_x = float(command.linear.x)
        angular_z = float(command.angular.z)
        left_rpm, right_rpm = self._compute_wheel_rpm(linear_x, angular_z)
        snapshot = self._wheel_estimator.update(left_rpm=left_rpm, right_rpm=right_rpm, dt_sec=dt_sec)

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

        chassis = ChassisState()
        chassis.left_rpm = float(left_rpm)
        chassis.right_rpm = float(right_rpm)
        chassis.linear_velocity = linear_x
        chassis.angular_velocity = angular_z
        chassis.estop = False
        chassis.comm_ok = True
        chassis.motor_enabled = not stale
        chassis.control_source = 'direct_driver_lane'
        chassis.heartbeat_ok = not stale
        chassis.driver_fault = False
        chassis.latched_fault_code = ''
        self.chassis_pub.publish(chassis)

        self._update_battery(linear_x=linear_x, now=now)
        low_warn = self._battery_percent <= 25.0
        low_stop = self._battery_percent <= 15.0
        power = PowerState()
        power.battery_voltage = float(self._battery_voltage)
        power.battery_percent = float(self._battery_percent)
        power.low_power_warn = bool(low_warn)
        power.low_power_stop = bool(low_stop)
        power.low_power_critical = bool(self._battery_percent <= 8.0)
        power.freshness_sec = 0.0
        power.power_level = 'low' if low_warn else 'normal'
        self._last_power = power
        self.power_pub.publish(power)

        battery = BatteryState()
        battery.header.stamp = stamp
        battery.voltage = power.battery_voltage
        battery.percentage = max(0.0, min(1.0, power.battery_percent / 100.0))
        battery.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        battery.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_GOOD
        self.battery_pub.publish(battery)

        system = SystemStatus()
        system.wifi_ok = bool(self.get_parameter('status_wifi_ok').value)
        system.camera_ok = bool(self.get_parameter('status_camera_ok').value)
        system.audio_ok = bool(self.get_parameter('status_audio_ok').value)
        system.uart_ok = bool(self.get_parameter('status_uart_ok').value)
        system.battery_voltage = power.battery_voltage
        system.battery_percent = power.battery_percent
        system.low_power_warn = power.low_power_warn
        system.low_power_stop = power.low_power_stop
        system.transport_degraded = stale
        system.stale_link = stale
        system.current_mode = ''
        self.system_pub.publish(system)

        self._last_update_at = now

    def publish_summary(self) -> None:
        """Publish summary payloads for hardware and bridge consumers.

        Returns:
            None.

        Raises:
            None.
        """
        boundary = self._boundary_snapshot.to_dict()
        command_age = max(0.0, monotonic_time() - self._last_cmd_at)
        stale = self._command_stale(now=monotonic_time())
        summary: dict[str, Any] = {
            'jointStateAvailable': self._latest_joint_state is not None,
            'batteryStateAvailable': self._last_power is not None,
            'cmdObserved': True,
            'descriptionLoaded': self._description_loaded,
            'robotName': self._description_robot_name,
            'boundary': boundary,
            'transportAuthority': boundary['transportAuthority'],
            'verificationStage': boundary['verificationStage'],
            'executionEvidenceClass': boundary['executionEvidenceClass'],
            'claimScope': boundary['claimScope'],
            'driverLanePackage': 'robot_direct_driver',
            'commandAgeSec': round(command_age, 3),
            'driverState': 'stale' if stale else 'running',
        }
        if self._last_power is not None:
            summary['batteryPercent'] = float(self._last_power.battery_percent)
            summary['batteryVoltage'] = float(self._last_power.battery_voltage)
        msg = String()
        msg.data = safe_json_dumps(summary)
        self.summary_pub.publish(msg)

        bridge_summary = {
            'connected': True,
            'state': 'direct_driver_active',
            'transport_degraded': stale,
            'reconnect_count': 0,
            'reconnect_state': 'not_applicable',
            'reconnect_retry_in_sec': 0.0,
            'reconnect_backoff_sec': 0.0,
            'protocol_errors': 0,
            'queue_depth': 0,
            'dropped_payloads': 0,
            'last_protocol_error': '',
            'last_disconnect_reason': '',
            'rx_age_sec': round(command_age, 3),
            'tx_age_sec': round(command_age, 3),
            'heartbeat_age_sec': round(command_age, 3),
            'last_rtt_ms': 0.0,
            'stale_link': stale,
            'inbound_rate_hz': float(self.get_parameter('driver_update_rate_hz').value),
            'outbound_rate_hz': float(self.get_parameter('driver_update_rate_hz').value),
            'current_mode': '',
            'host': 'direct_driver_lane',
            'port': 0,
            'odom': None,
            'battery_voltage': float(self._battery_voltage),
            'battery_percent': float(self._battery_percent),
            'low_power_warn': bool(self._battery_percent <= 25.0),
            'low_power_stop': bool(self._battery_percent <= 15.0),
            'wifi_ok': bool(self.get_parameter('status_wifi_ok').value),
            'camera_ok': bool(self.get_parameter('status_camera_ok').value),
            'audio_ok': bool(self.get_parameter('status_audio_ok').value),
            'uart_ok': bool(self.get_parameter('status_uart_ok').value),
            'control_source': 'direct_driver_lane',
            'estop': False,
            'heartbeat_ok': not stale,
        }
        bridge_msg = String()
        bridge_msg.data = safe_json_dumps(bridge_summary)
        self.bridge_summary_pub.publish(bridge_msg)


def main() -> None:
    rclpy.init()
    node = DirectDriverNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
