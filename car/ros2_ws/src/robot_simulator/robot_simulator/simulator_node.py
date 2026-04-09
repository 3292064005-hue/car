from __future__ import annotations

import json

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String

from robot_msgs.msg import ChassisState, PowerState, SystemStatus
from robot_utils.helpers import monotonic_time, safe_json_dumps
from robot_utils.qos_profiles import qos_for
from .simulator_model import DifferentialDriveState, step_simulation


class RobotSimulatorNode(Node):
    """ROS-side deterministic simulator used for integration and release gating.

    The simulator replaces the TCP mock path with an auditable, in-repo dynamics
    model that publishes the same domain-specific telemetry expected by the current
    control, monitor, and web layers.
    """

    def __init__(self) -> None:
        super().__init__('robot_simulator')
        self.declare_parameter('publish_rate_hz', 20.0)
        self.declare_parameter('command_timeout_sec', 0.8)
        self.declare_parameter('moving_drain_per_sec', 0.35)
        self.declare_parameter('idle_drain_per_sec', 0.02)
        self.declare_parameter('bridge_summary_topic', '/robot/bridge/summary')
        self.declare_parameter('transport_stats_topic', '/robot/bridge/transport_stats')

        self._state = DifferentialDriveState()
        self._last_cmd = Twist()
        self._last_cmd_at = monotonic_time()
        self._last_step_at = monotonic_time()

        self.chassis_pub = self.create_publisher(ChassisState, '/robot/chassis_state', qos_for('telemetry'))
        self.power_pub = self.create_publisher(PowerState, '/robot/power_state', qos_for('telemetry'))
        self.system_pub = self.create_publisher(SystemStatus, '/robot/system_status', qos_for('telemetry'))
        self.bridge_summary_pub = self.create_publisher(String, str(self.get_parameter('bridge_summary_topic').value), qos_for('status_summary'))
        self.transport_stats_pub = self.create_publisher(String, str(self.get_parameter('transport_stats_topic').value), qos_for('status_summary'))
        self.create_subscription(Twist, '/robot/cmd_vel_final', self.on_cmd_vel, qos_for('control_cmd'))
        self.timer = self.create_timer(1.0 / float(self.get_parameter('publish_rate_hz').value), self.step)

    def on_cmd_vel(self, msg: Twist) -> None:
        self._last_cmd = msg
        self._last_cmd_at = monotonic_time()

    def step(self) -> None:
        """Advance the simulator, then publish chassis, power, and bridge health.

        Returns:
            None.

        Raises:
            None. Stale commands are converted into a zero-velocity step.
        """
        now = monotonic_time()
        dt_sec = max(0.0, now - self._last_step_at)
        self._last_step_at = now
        stale = now - self._last_cmd_at > float(self.get_parameter('command_timeout_sec').value)
        linear = 0.0 if stale else float(self._last_cmd.linear.x)
        angular = 0.0 if stale else float(self._last_cmd.angular.z)
        self._state = step_simulation(
            state=self._state,
            linear_cmd=linear,
            angular_cmd=angular,
            dt_sec=dt_sec,
            moving_drain_per_sec=float(self.get_parameter('moving_drain_per_sec').value),
            idle_drain_per_sec=float(self.get_parameter('idle_drain_per_sec').value),
        )

        chassis = ChassisState()
        chassis.linear_velocity = self._state.linear_velocity
        chassis.angular_velocity = self._state.angular_velocity
        chassis.left_rpm = (self._state.linear_velocity - self._state.angular_velocity * 0.16) * 60.0
        chassis.right_rpm = (self._state.linear_velocity + self._state.angular_velocity * 0.16) * 60.0
        chassis.estop = False
        chassis.comm_ok = True
        chassis.motor_enabled = True
        chassis.control_source = 'simulator'
        chassis.heartbeat_ok = True
        self.chassis_pub.publish(chassis)

        power = PowerState()
        power.battery_voltage = self._state.battery_voltage
        power.battery_percent = self._state.battery_percent
        power.low_power_warn = self._state.battery_percent <= 25.0
        power.low_power_stop = self._state.battery_percent <= 10.0
        self.power_pub.publish(power)

        system = SystemStatus()
        system.wifi_ok = True
        system.camera_ok = True
        system.audio_ok = True
        system.uart_ok = True
        system.battery_voltage = self._state.battery_voltage
        system.current_mode = 'SIM'
        system.low_power_warn = power.low_power_warn
        system.low_power_stop = power.low_power_stop
        self.system_pub.publish(system)

        bridge_summary = String()
        bridge_summary.data = safe_json_dumps({
            'connected': True,
            'last_rtt_ms': 0.0,
            'heartbeat_age_sec': 0.0,
            'reconnect_count': 0,
            'mode': 'simulator',
        })
        self.bridge_summary_pub.publish(bridge_summary)

        transport_stats = String()
        transport_stats.data = safe_json_dumps({
            'stale_link': False,
            'inbound_rate_hz': float(self.get_parameter('publish_rate_hz').value),
            'outbound_rate_hz': float(self.get_parameter('publish_rate_hz').value),
        })
        self.transport_stats_pub.publish(transport_stats)


def main() -> None:
    rclpy.init()
    node = RobotSimulatorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
