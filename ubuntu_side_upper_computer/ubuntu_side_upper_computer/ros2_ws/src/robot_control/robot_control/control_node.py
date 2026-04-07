from __future__ import annotations

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from robot_msgs.msg import ChassisState, EventLog, Fault, ModeState, PowerState
from robot_contracts.runtime_param_transport import (
    RUNTIME_PARAM_APPLY_RESULT_TOPIC,
    RUNTIME_PARAM_TOPIC,
    build_runtime_param_apply_result,
    dumps_runtime_param_apply_result,
    loads_runtime_param_payload,
)
from robot_control.arbiter import select_command, zero_twist
from robot_control.control_state import ControlSelection, TimedTwist
from robot_control.limiter import limit_twist
from robot_control.power_guard import apply_power_guard
from robot_control.ramp import apply_ramp
from robot_control.safety_guard import apply_safety
from robot_control.source_timeout import source_age_sec
from robot_utils.constants import MODE_IDLE, MODE_TRACK
from robot_utils.helpers import monotonic_time, safe_json_dumps
from robot_utils.error_policy import classify_exception, publish_policy_outcome
from robot_utils.qos_profiles import qos_for


class ControlNode(Node):
    def __init__(self) -> None:
        super().__init__('robot_control')
        self.declare_parameter('max_linear', 0.30)
        self.declare_parameter('max_angular', 1.20)
        self.declare_parameter('reverse_max_linear', 0.18)
        self.declare_parameter('turn_slowdown_ratio', 0.5)
        self.declare_parameter('track_linear_scale', 0.70)
        self.declare_parameter('track_angular_scale', 0.85)
        self.declare_parameter('publish_rate_hz', 20.0)
        self.declare_parameter('manual_timeout_sec', 0.6)
        self.declare_parameter('patrol_timeout_sec', 0.8)
        self.declare_parameter('track_timeout_sec', 0.5)
        self.declare_parameter('chassis_timeout_sec', 0.8)
        self.declare_parameter('power_timeout_sec', 2.0)
        self.declare_parameter('fault_hold_sec', 0.35)
        self.declare_parameter('max_linear_step', 0.05)
        self.declare_parameter('max_angular_step', 0.12)
        self.declare_parameter('resume_linear_step', 0.03)
        self.declare_parameter('resume_angular_step', 0.08)
        self.declare_parameter('low_power_linear_scale', 0.5)
        self.declare_parameter('low_power_angular_scale', 0.8)

        self.manual_cmd = TimedTwist()
        self.patrol_cmd = TimedTwist()
        self.track_cmd = TimedTwist()
        self.mode: str = MODE_IDLE
        self.last_fault: Fault | None = None
        self.last_fault_at: float = 0.0
        self.fault_hold_until: float = 0.0
        self.chassis_state: ChassisState | None = None
        self.chassis_state_at: float = 0.0
        self.power_state: PowerState | None = None
        self.power_state_at: float = 0.0
        self.last_output = zero_twist()
        self.selection = ControlSelection()
        self.runtime_param_overrides: dict[str, float] = {}

        self.pub = self.create_publisher(Twist, '/robot/cmd_vel_final', qos_for('control_cmd'))
        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self.source_pub = self.create_publisher(String, '/robot/control/source', qos_for('status_summary'))
        self.summary_pub = self.create_publisher(String, '/robot/control/summary', qos_for('status_summary'))
        self.runtime_param_apply_pub = self.create_publisher(String, RUNTIME_PARAM_APPLY_RESULT_TOPIC, qos_for('status_summary'))
        self.create_subscription(Twist, '/robot/manual/cmd_vel', self.on_manual, qos_for('control_cmd'))
        self.create_subscription(Twist, '/robot/patrol/cmd_vel', self.on_patrol, qos_for('control_cmd'))
        self.create_subscription(Twist, '/robot/track/cmd_vel', self.on_track, qos_for('control_cmd'))
        self.create_subscription(ModeState, '/robot/mode_state', self.on_mode, qos_for('mode_state'))
        self.create_subscription(Fault, '/robot/fault', self.on_fault, qos_for('fault_event'))
        self.create_subscription(ChassisState, '/robot/chassis_state', self.on_chassis, qos_for('telemetry'))
        self.create_subscription(PowerState, '/robot/power_state', self.on_power, qos_for('telemetry'))
        self.create_subscription(String, RUNTIME_PARAM_TOPIC, self.on_runtime_params, qos_for('status_summary'))

        rate_hz = float(self.get_parameter('publish_rate_hz').value)
        self.timer = self.create_timer(1.0 / rate_hz, self.publish_final_cmd)
        self.get_logger().info('robot_control started')

    def _store_timed_twist(self, holder: TimedTwist, msg: Twist) -> None:
        holder.cmd = msg
        holder.stamp = monotonic_time()
        holder.valid = True

    def on_manual(self, msg: Twist) -> None:
        self._store_timed_twist(self.manual_cmd, msg)

    def on_patrol(self, msg: Twist) -> None:
        self._store_timed_twist(self.patrol_cmd, msg)

    def on_track(self, msg: Twist) -> None:
        self._store_timed_twist(self.track_cmd, msg)

    def on_mode(self, msg: ModeState) -> None:
        self.mode = msg.current_mode or MODE_IDLE

    def on_fault(self, msg: Fault) -> None:
        self.last_fault = msg
        self.last_fault_at = monotonic_time()
        if msg.level in {'error', 'fatal'}:
            self.fault_hold_until = max(self.fault_hold_until, self.last_fault_at + float(self.get_parameter('fault_hold_sec').value))

    def on_chassis(self, msg: ChassisState) -> None:
        self.chassis_state = msg
        self.chassis_state_at = monotonic_time()

    def on_power(self, msg: PowerState) -> None:
        self.power_state = msg
        self.power_state_at = monotonic_time()

    def _publish_runtime_param_apply_result(self, payload: dict[str, object]) -> None:
        """Publish one runtime-parameter apply acknowledgement for bridge aggregation.

        Args:
            payload: JSON-serializable apply-result payload.

        Returns:
            None.

        Raises:
            None. Publishing failures are intentionally swallowed because control
            delivery must not fail while emitting status telemetry.
        """
        try:
            msg = String()
            msg.data = dumps_runtime_param_apply_result(payload)
            self.runtime_param_apply_pub.publish(msg)
        except Exception:
            return

    def on_runtime_params(self, msg: String) -> None:
        """Apply runtime-parameter overrides received from the web bridge.

        Args:
            msg: Runtime-parameter synchronization payload.

        Returns:
            None.

        Raises:
            None.
        """
        try:
            payload = loads_runtime_param_payload(msg.data)
        except Exception as exc:
            publish_policy_outcome(self, outcome=classify_exception('control.runtime_params', exc, code='CONTROL_RUNTIME_PARAMS_INVALID', operator_message='control runtime parameter sync failed'), event_pub=self.event_pub)
            ControlNode._publish_runtime_param_apply_result(self, build_runtime_param_apply_result(
                consumer='robot_control',
                transaction_id='',
                runtime_param_version=0,
                ok=False,
                message=f'control runtime parameter sync failed: {exc}',
                ts='',
            ))
            return
        params = payload.get('params', {})
        if not isinstance(params, dict):
            publish_policy_outcome(self, outcome=classify_exception('control.runtime_params', TypeError('params must be an object'), code='CONTROL_RUNTIME_PARAMS_INVALID', operator_message='control runtime parameter sync failed'), event_pub=self.event_pub)
            ControlNode._publish_runtime_param_apply_result(self, build_runtime_param_apply_result(
                consumer='robot_control',
                transaction_id=str(payload.get('transaction_id', '') or ''),
                runtime_param_version=int(payload.get('runtime_param_version', 0) or 0),
                ok=False,
                message='control runtime parameter sync failed: params must be an object',
                ts=str(payload.get('ts', '') or ''),
                trace_id=str(payload.get('trace_id', '') or ''),
            ))
            return
        self.runtime_param_overrides = dict(params)
        self._publish_runtime_param_apply_result(build_runtime_param_apply_result(
            consumer='robot_control',
            transaction_id=str(payload.get('transaction_id', '') or ''),
            runtime_param_version=int(payload.get('runtime_param_version', 0) or 0),
            ok=True,
            message='control runtime parameters applied',
            ts=str(payload.get('ts', '') or ''),
            trace_id=str(payload.get('trace_id', '') or ''),
        ))

    def _runtime_param_value(self, key: str, fallback: float) -> float:
        """Resolve one runtime override with a safe fallback.

        Args:
            key: Runtime parameter key.
            fallback: Fallback value.

        Returns:
            Effective runtime value.

        Raises:
            None.
        """
        raw = self.runtime_param_overrides.get(key, fallback)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(fallback)

    def publish_final_cmd(self) -> None:
        source, selected = select_command(
            self.mode,
            self.manual_cmd,
            self.patrol_cmd,
            self.track_cmd,
            manual_timeout_sec=float(self.get_parameter('manual_timeout_sec').value),
            patrol_timeout_sec=float(self.get_parameter('patrol_timeout_sec').value),
            track_timeout_sec=float(self.get_parameter('track_timeout_sec').value),
        )
        selected_age = {
            'manual': source_age_sec(self.manual_cmd),
            'patrol': source_age_sec(self.patrol_cmd),
            'track': source_age_sec(self.track_cmd),
        }.get(source, 0.0)
        max_linear = self._runtime_param_value('maxLinearSpeed', float(self.get_parameter('max_linear').value))
        max_angular = self._runtime_param_value('maxAngularSpeed', float(self.get_parameter('max_angular').value))
        limited = limit_twist(
            selected,
            max_linear=max_linear,
            max_angular=max_angular,
            reverse_max_linear=float(self.get_parameter('reverse_max_linear').value),
            turn_slowdown_ratio=float(self.get_parameter('turn_slowdown_ratio').value),
            track_linear_scale=float(self.get_parameter('track_linear_scale').value),
            track_angular_scale=float(self.get_parameter('track_angular_scale').value),
            mode=self.mode,
        )
        linear_step = float(self.get_parameter('resume_linear_step').value) if abs(self.last_output.linear.x) < 1e-6 else float(self.get_parameter('max_linear_step').value)
        angular_step = float(self.get_parameter('resume_angular_step').value) if abs(self.last_output.angular.z) < 1e-6 else float(self.get_parameter('max_angular_step').value)
        ramped = apply_ramp(self.last_output, limited, max_linear_step=linear_step, max_angular_step=angular_step)
        chassis_age_sec = float('inf') if self.chassis_state_at == 0.0 else monotonic_time() - self.chassis_state_at
        power_age_sec = float('inf') if self.power_state_at == 0.0 else monotonic_time() - self.power_state_at
        safe, safety_latched, safety_reason = apply_safety(
            ramped,
            self.mode,
            self.chassis_state,
            self.last_fault,
            chassis_state_stale=chassis_age_sec > float(self.get_parameter('chassis_timeout_sec').value),
            fault_hold_active=monotonic_time() < self.fault_hold_until,
            include_reason=True,
        )
        final, power_limited, power_reason = apply_power_guard(
            safe,
            self.power_state,
            low_power_linear_scale=float(self.get_parameter('low_power_linear_scale').value),
            low_power_angular_scale=float(self.get_parameter('low_power_angular_scale').value),
            include_reason=True,
            power_state_stale=power_age_sec > float(self.get_parameter('power_timeout_sec').value),
        )

        self.selection.source = source
        self.selection.selected = selected
        self.selection.limited = limited
        self.selection.ramped = ramped
        self.selection.final = final
        self.selection.selected_age_sec = 0.0 if selected_age == float('inf') else selected_age
        self.selection.chassis_age_sec = chassis_age_sec
        self.selection.power_age_sec = power_age_sec
        self.selection.safety_latched = safety_latched
        self.selection.safety_reason = safety_reason
        self.selection.power_limited = power_limited
        self.selection.power_reason = power_reason
        self.last_output = final

        self.pub.publish(final)
        source_msg = String()
        source_msg.data = source
        self.source_pub.publish(source_msg)
        summary = String()
        summary.data = safe_json_dumps({
            'mode': self.mode,
            'source': source,
            'selected_age_sec': round(float(self.selection.selected_age_sec), 4),
            'chassis_age_sec': None if chassis_age_sec == float('inf') else round(float(chassis_age_sec), 4),
            'power_age_sec': None if power_age_sec == float('inf') else round(float(power_age_sec), 4),
            'safety_latched': safety_latched,
            'safety_reason': safety_reason,
            'fault_hold_active': monotonic_time() < self.fault_hold_until,
            'power_limited': power_limited,
            'power_reason': power_reason,
            'vx': round(float(final.linear.x), 4),
            'wz': round(float(final.angular.z), 4),
            'track_mode': self.mode == MODE_TRACK,
        })
        self.summary_pub.publish(summary)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ControlNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
