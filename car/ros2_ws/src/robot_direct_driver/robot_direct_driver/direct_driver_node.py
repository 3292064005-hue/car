from __future__ import annotations

from pathlib import Path
from typing import Any
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import BatteryState, JointState
from std_msgs.msg import String

from robot_bridge.command_payloads import build_cmd_vel_payload, build_mode_payload
from robot_bridge.components.protocol_layer import BridgeProtocolLayer
from robot_bridge.protocol_policy import canonical_payload_type
from robot_bridge.runtime_factory import build_transport_stack, declare_transport_parameters
from robot_bridge.translators import payload_to_chassis, payload_to_fault, payload_to_power, payload_to_status
from robot_description.description_model import load_description_model
from robot_hardware_interface.hardware_adapter import WheelDriveEstimator, build_hardware_boundary_snapshot
from robot_hardware_interface.hardware_contract import HARDWARE_RUNTIME_CONTRACT_VERSION
from robot_hardware_interface.standardization_target import hardware_standardization_target
from robot_msgs.msg import ChassisState, EventLog, Fault, ModeState, PowerState, SystemStatus
from robot_utils.constants import FAULT_LEVEL_ERROR, FAULT_LINK
from robot_utils.helpers import monotonic_time, safe_json_dumps
from robot_utils.message_factory import make_event
from robot_utils.qos_profiles import qos_for
from robot_utils.error_policy import build_policy_outcome, publish_policy_outcome


class DirectDriverNode(Node):
    """ROS soft/verified board-driver runtime for governed hardware lanes.

    The node consumes the final command arbitration result from ``robot_control``
    and speaks the board transport protocol directly. All chassis/power/status
    telemetry now originates from the transport/protocol path instead of being
    fabricated inside a local projection loop.
    """

    def __init__(self) -> None:
        super().__init__('robot_direct_driver')
        self.declare_parameter('joint_state_topic', '/joint_states')
        self.declare_parameter('battery_state_topic', '/battery_state')
        self.declare_parameter('cmd_vel_observed_topic', '/robot/hardware/cmd_vel_observed')
        self.declare_parameter('enable_cmd_vel_alias', False)
        self.declare_parameter('summary_topic', '/robot/hardware_interface/summary')
        self.declare_parameter('bridge_summary_topic', '/robot/bridge/summary')
        self.declare_parameter('chassis_state_topic', '/robot/chassis_state')
        self.declare_parameter('power_state_topic', '/robot/power_state')
        self.declare_parameter('system_status_topic', '/robot/system_status')
        self.declare_parameter('description_path', '')
        self.declare_parameter('hardware_interface_config_path', '')
        self.declare_parameter('bridge_config_path', '')
        self.declare_parameter('left_wheel_joint_name', 'left_wheel_joint')
        self.declare_parameter('right_wheel_joint_name', 'right_wheel_joint')
        self.declare_parameter('compatibility_surface_role', 'ros_soft_driver')
        self.declare_parameter('board_validation_in_repo', False)
        self.declare_parameter('board_execution_confirmed', False)
        self.declare_parameter('feedback_source', 'direct_board_feedback')
        self.declare_parameter('actuation_boundary', 'inside_ros_driver')
        self.declare_parameter('transport_authority', 'ros_process_driver')
        self.declare_parameter('verification_stage', 'host_harness_only')
        self.declare_parameter('command_transport', 'direct_driver_loop')
        self.declare_parameter('verification_artifact_path', '')
        self.declare_parameter('direct_driver_lane_policy', 'separate_package_required')
        self.declare_parameter('summary_rate_hz', 2.0)
        self.declare_parameter('command_timeout_sec', 1.0)
        declare_transport_parameters(self)

        self.seq = 0
        self.current_mode = 'IDLE'
        self.link_fault_active = False
        self._latest_cmd = Twist()
        self._last_cmd_at = monotonic_time()
        self._last_rx_at = 0.0
        self._last_joint_at = monotonic_time()
        self._latest_joint_state: JointState | None = None
        self._latest_chassis: ChassisState | None = None
        self._latest_power: PowerState | None = None
        self._latest_status: SystemStatus | None = None
        self._wheel_estimator = WheelDriveEstimator()

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

        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self.fault_pub = self.create_publisher(Fault, '/robot/fault', qos_for('fault_event'))
        self.cmd_pub = self.create_publisher(Twist, cmd_vel_observed_topic, qos_for('control_cmd'))
        self.joint_pub = self.create_publisher(JointState, str(self.get_parameter('joint_state_topic').value), qos_for('telemetry'))
        self.battery_pub = self.create_publisher(BatteryState, str(self.get_parameter('battery_state_topic').value), qos_for('telemetry'))
        self.summary_pub = self.create_publisher(String, str(self.get_parameter('summary_topic').value), qos_for('status_summary'))
        self.bridge_summary_pub = self.create_publisher(String, str(self.get_parameter('bridge_summary_topic').value), qos_for('status_summary'))
        self.chassis_pub = self.create_publisher(ChassisState, str(self.get_parameter('chassis_state_topic').value), qos_for('telemetry'))
        self.power_pub = self.create_publisher(PowerState, str(self.get_parameter('power_state_topic').value), qos_for('telemetry'))
        self.system_pub = self.create_publisher(SystemStatus, str(self.get_parameter('system_status_topic').value), qos_for('telemetry'))

        stack = build_transport_stack(self, next_seq=self.next_seq, logger=self.get_logger())
        self.host = stack.host
        self.port = stack.port
        self.health = stack.health
        self.reconnect = stack.reconnect
        self.heartbeat = stack.heartbeat
        self.transport = stack.transport
        self.protocol = BridgeProtocolLayer(
            health=self.health,
            logger=self.get_logger(),
            protocol_fault_threshold=3,
            on_payload=self._on_protocol_payload,
            on_warn=self._on_protocol_warn,
            on_fault=self._on_protocol_fault,
        )

        self.create_subscription(Twist, '/robot/cmd_vel_final', self.on_final_cmd, qos_for('control_cmd'))
        self.create_subscription(ModeState, '/robot/mode_state', self.on_mode_state, qos_for('mode_state'))
        self.create_timer(0.20, self.ensure_connection)
        self.create_timer(0.05, self.poll_socket)
        self.create_timer(float(self.get_parameter('heartbeat_period').value), self.send_heartbeat)
        self.create_timer(1.0 / max(0.1, float(self.get_parameter('summary_rate_hz').value)), self.publish_summary)
        self.get_logger().info(f'robot_direct_driver connecting to {self.host}:{self.port}')

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def publish_event(self, category: str, name: str, detail: str, level: str = 'info') -> None:
        self.event_pub.publish(make_event(self, category, name, detail, level=level))

    def handle_link_fault(self, description: str) -> None:
        if self.link_fault_active:
            return
        publish_policy_outcome(
            self,
            outcome=build_policy_outcome(
                code=FAULT_LINK,
                source='direct_driver.transport',
                disposition='degraded',
                operator_message=description,
                event_name='direct_driver_link_fault',
                event_level='error',
                recoverable=True,
                fault_level=FAULT_LEVEL_ERROR,
                evidence_reference='direct_driver_transport',
            ),
            event_pub=self.event_pub,
            fault_pub=self.fault_pub,
            fault_source='robot_direct_driver',
        )
        self.link_fault_active = True

    def ensure_connection(self) -> None:
        self.transport.ensure_connection(
            on_connected=lambda: self.publish_event('hardware', 'connected', 'direct-driver transport connected'),
            on_link_fault=self.handle_link_fault,
        )
        if self.transport.is_connected():
            self.link_fault_active = False

    def on_mode_state(self, msg: ModeState) -> None:
        self.current_mode = str(msg.current_mode or 'IDLE')
        payload = build_mode_payload(
            seq=self.next_seq(),
            mode=self.current_mode,
            requested_by=str(getattr(msg, 'requested_by', '') or 'direct_driver'),
            reason=str(getattr(msg, 'reason', '') or 'mode_update'),
        )
        self.transport.enqueue(payload)

    def _resolve_cmd_vel_observed_topic(self) -> str:
        """Resolve the non-authoritative observed command topic.

        Args:
            None.

        Returns:
            The topic used to mirror the final command for ROS tooling.

        Raises:
            ValueError: When a config attempts to publish ``/cmd_vel`` without
                the explicit ``enable_cmd_vel_alias`` compatibility opt-in.

        Boundary behavior:
            ``/robot/cmd_vel_final`` remains the project-owned authoritative
            control output. The observed topic is a projection/diagnostic
            surface. Publishing the external ``/cmd_vel`` alias is disabled
            by default so external controllers cannot mistake projection for
            command authority.
        """
        topic = str(self.get_parameter('cmd_vel_observed_topic').value or '').strip() or '/robot/hardware/cmd_vel_observed'
        alias_enabled = bool(self.get_parameter('enable_cmd_vel_alias').value)
        if topic == '/cmd_vel' and not alias_enabled:
            raise ValueError('cmd_vel_observed_topic=/cmd_vel requires enable_cmd_vel_alias=true; /robot/cmd_vel_final remains authoritative')
        return topic

    def on_final_cmd(self, msg: Twist) -> None:
        """Forward the final control command to the board transport and optional observed surface.

        Args:
            msg: Arbitration result emitted by ``robot_control``.

        Returns:
            None.

        Raises:
            None. Queue/transport faults are surfaced asynchronously via the
            transport summary and policy fault channel.
        """
        self._latest_cmd = msg
        self._last_cmd_at = monotonic_time()
        self.cmd_pub.publish(msg)
        payload = build_cmd_vel_payload(
            seq=self.next_seq(),
            vx=float(msg.linear.x),
            wz=float(msg.angular.z),
            mode=self.current_mode,
        )
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
            self.protocol.process_line(line)
        self.transport.flush()

    def _on_protocol_warn(self, reason: str) -> None:
        self.publish_event('hardware', 'protocol_warn', reason, level='warn')

    def _on_protocol_fault(self, reason: str) -> None:
        publish_policy_outcome(
            self,
            outcome=build_policy_outcome(
                code='DIRECT_DRIVER_PROTOCOL_FAULT',
                source='direct_driver.protocol',
                disposition='degraded',
                operator_message=reason,
                event_name='direct_driver_protocol_fault',
                event_level='error',
                recoverable=True,
                fault_level=FAULT_LEVEL_ERROR,
                evidence_reference='direct_driver_protocol_layer',
            ),
            event_pub=self.event_pub,
            fault_pub=self.fault_pub,
            fault_source='robot_direct_driver',
        )

    def _publish_joint_state_from_chassis(self, chassis: ChassisState) -> None:
        now = monotonic_time()
        dt_sec = max(0.0, now - self._last_joint_at)
        self._last_joint_at = now
        snapshot = self._wheel_estimator.update(
            left_rpm=float(chassis.left_rpm),
            right_rpm=float(chassis.right_rpm),
            dt_sec=dt_sec,
        )
        joint = JointState()
        joint.header.stamp = self.get_clock().now().to_msg()
        joint.name = [
            str(self.get_parameter('left_wheel_joint_name').value),
            str(self.get_parameter('right_wheel_joint_name').value),
        ]
        joint.position = [snapshot.left_position_rad, snapshot.right_position_rad]
        joint.velocity = [snapshot.left_velocity_rad_s, snapshot.right_velocity_rad_s]
        self._latest_joint_state = joint
        self.joint_pub.publish(joint)

    def _publish_battery_state_from_power(self, power: PowerState) -> None:
        battery = BatteryState()
        battery.header.stamp = self.get_clock().now().to_msg()
        battery.voltage = float(power.battery_voltage)
        battery.percentage = max(0.0, min(1.0, float(power.battery_percent) / 100.0))
        battery.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        battery.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_GOOD
        if bool(getattr(power, 'low_power_stop', False)):
            battery.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_DEAD
        elif bool(getattr(power, 'low_power_warn', False)):
            battery.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_UNSPEC_FAILURE
        self.battery_pub.publish(battery)

    def _on_protocol_payload(self, payload: dict[str, Any]) -> None:
        payload_type = canonical_payload_type(payload)
        if payload_type == 'pong':
            seq = payload.get('seq')
            self.transport.mark_pong(int(seq) if seq is not None else None)
            return
        self._last_rx_at = monotonic_time()
        if payload_type == 'chassis_state':
            chassis = payload_to_chassis(payload)
            self._latest_chassis = chassis
            self.chassis_pub.publish(chassis)
            self._publish_joint_state_from_chassis(chassis)
            return
        if payload_type == 'power_state':
            power = payload_to_power(payload)
            self._latest_power = power
            self.power_pub.publish(power)
            self._publish_battery_state_from_power(power)
            return
        if payload_type == 'system_status':
            status = payload_to_status(payload)
            self._latest_status = status
            self.system_pub.publish(status)
            return
        if payload_type == 'fault':
            self.fault_pub.publish(payload_to_fault(self, payload))
            return

    def _command_stale(self, *, now: float) -> bool:
        timeout_sec = float(self.get_parameter('command_timeout_sec').value)
        return timeout_sec > 0.0 and (now - self._last_cmd_at) > timeout_sec

    def publish_summary(self) -> None:
        """Publish authoritative hardware/transport summary surfaces.

        Returns:
            None.

        Raises:
            None.
        """
        now = monotonic_time()
        boundary = self._boundary_snapshot.to_dict(deployment_tier='real_robot')
        runtime_contract = boundary.get('runtimeContract', {}) if isinstance(boundary.get('runtimeContract'), dict) else {}
        command_age = max(0.0, now - self._last_cmd_at)
        rx_age = max(0.0, now - self._last_rx_at) if self._last_rx_at else None
        stale = self._command_stale(now=now)
        transport_summary = self.health.summary()
        reconnect = self.transport.reconnect_summary()
        heartbeat_age = self.transport.heartbeat_age()
        bridge_summary = {
            **transport_summary,
            **reconnect,
            'state': 'connected' if self.transport.is_connected() else 'disconnected',
            'connected': bool(self.transport.is_connected()),
            'last_rtt_ms': round(self.transport.last_rtt_ms(), 3),
            'heartbeat_age_sec': round(heartbeat_age, 3) if heartbeat_age is not None else None,
            'stale_link': bool(heartbeat_age is not None and heartbeat_age > float(self.get_parameter('heartbeat_timeout_sec').value)),
            'current_mode': self.current_mode,
            'host': self.host,
            'port': self.port,
            'transport_degraded': bool(transport_summary.get('transport_degraded', False)),
            'rx_age_sec': round(rx_age, 3) if rx_age is not None else None,
            'tx_age_sec': round(command_age, 3),
            'cmdVelObservedTopic': str(self.get_parameter('cmd_vel_observed_topic').value),
            'cmdVelAliasEnabled': bool(self.get_parameter('enable_cmd_vel_alias').value),
            'commandAuthorityTopic': '/robot/cmd_vel_final',
            'externalCompatibilityAliasTopic': '/cmd_vel' if bool(self.get_parameter('enable_cmd_vel_alias').value) else None,
            'control_source': self._latest_chassis.control_source if self._latest_chassis is not None else 'direct_driver_lane',
            'estop': bool(self._latest_chassis.estop) if self._latest_chassis is not None else False,
            'heartbeat_ok': bool(self._latest_chassis.heartbeat_ok) if self._latest_chassis is not None else False,
        }
        if self._latest_power is not None:
            bridge_summary.update({
                'battery_voltage': float(self._latest_power.battery_voltage),
                'battery_percent': float(self._latest_power.battery_percent),
                'low_power_warn': bool(self._latest_power.low_power_warn),
                'low_power_stop': bool(self._latest_power.low_power_stop),
            })
        if self._latest_status is not None:
            bridge_summary.update({
                'wifi_ok': bool(self._latest_status.wifi_ok),
                'camera_ok': bool(self._latest_status.camera_ok),
                'audio_ok': bool(self._latest_status.audio_ok),
                'uart_ok': bool(self._latest_status.uart_ok),
            })

        standardization_target = hardware_standardization_target(str(boundary.get('effectiveCompatibilitySurfaceRole', boundary.get('compatibilitySurfaceRole', 'ros_soft_driver'))))
        artifact_paths = standardization_target.get('artifactPaths', {}) if isinstance(standardization_target.get('artifactPaths', {}), dict) else {}
        standardization_artifacts = {key: str((Path(__file__).resolve().parents[4] / str(rel)).resolve()) for key, rel in artifact_paths.items()}
        standardization_artifacts_present = {key: Path(path).is_file() for key, path in standardization_artifacts.items()}
        summary: dict[str, Any] = {
            'jointStateAvailable': self._latest_joint_state is not None,
            'batteryStateAvailable': self._latest_power is not None,
            'cmdObserved': True,
            'descriptionLoaded': self._description_loaded,
            'robotName': self._description_robot_name,
            'boundary': boundary,
            'runtimeContractVersion': runtime_contract.get('contractVersion', HARDWARE_RUNTIME_CONTRACT_VERSION),
            'hardwareDomains': runtime_contract.get('domains', []),
            'commandAuthorityInsideRos': runtime_contract.get('commandAuthorityInsideRos', True),
            'telemetryAuthorityInsideRos': runtime_contract.get('telemetryAuthorityInsideRos', True),
            'transportAuthority': boundary['transportAuthority'],
            'verificationStage': boundary['verificationStage'],
            'executionEvidenceClass': boundary['executionEvidenceClass'],
            'claimScope': boundary['claimScope'],
            'standardizationTarget': standardization_target,
            'standardizationArtifacts': standardization_artifacts,
            'standardizationArtifactsPresent': standardization_artifacts_present,
            'driverLanePackage': 'robot_direct_driver',
            'commandAgeSec': round(command_age, 3),
            'rxAgeSec': round(rx_age, 3) if rx_age is not None else None,
            'driverState': bridge_summary['state'],
            'transportSummary': bridge_summary,
            'bridgeSummaryTopic': str(self.get_parameter('bridge_summary_topic').value),
            'bridgeConfigPath': str(self.get_parameter('bridge_config_path').value or ''),
            'commandStale': stale,
        }
        if self._latest_chassis is not None:
            summary['chassis'] = {
                'leftRpm': float(self._latest_chassis.left_rpm),
                'rightRpm': float(self._latest_chassis.right_rpm),
                'linearVelocity': float(self._latest_chassis.linear_velocity),
                'angularVelocity': float(self._latest_chassis.angular_velocity),
                'commOk': bool(self._latest_chassis.comm_ok),
                'motorEnabled': bool(self._latest_chassis.motor_enabled),
            }
        if self._latest_power is not None:
            summary['batteryPercent'] = float(self._latest_power.battery_percent)
            summary['batteryVoltage'] = float(self._latest_power.battery_voltage)

        msg = String(); msg.data = safe_json_dumps(summary)
        self.summary_pub.publish(msg)
        bridge_msg = String(); bridge_msg.data = safe_json_dumps(bridge_summary)
        self.bridge_summary_pub.publish(bridge_msg)


def main() -> None:
    rclpy.init()
    node = DirectDriverNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
