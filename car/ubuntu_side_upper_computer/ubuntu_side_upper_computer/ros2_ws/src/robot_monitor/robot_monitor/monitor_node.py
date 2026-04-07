from __future__ import annotations

import json
import math

import rclpy
try:
    from rclpy.executors import MultiThreadedExecutor
except Exception:  # pragma: no cover
    MultiThreadedExecutor = None
from rclpy.node import Node
from std_msgs.msg import String
from robot_msgs.msg import ChassisState, EventLog, Fault, ModeState, PowerState, SystemStatus, VoiceCommand
from robot_monitor.dashboard_adapter import render_text
from robot_monitor.diagnostics_adapter import DiagnosticArray, diagnostic_transport_type, make_diagnostic_status, make_diagnostic_statuses
from robot_monitor.event_logger import EvidenceIndex, JsonlEventLogger
from robot_monitor.metrics import Metrics
from robot_monitor.status_aggregator import StatusSnapshot, derive_readiness
from robot_contracts.runtime_param_transport import RUNTIME_PARAM_TOPIC, loads_runtime_param_payload
from robot_utils.qos_profiles import qos_for
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.error_policy import classify_exception, publish_policy_outcome


class MonitorNode(Node):
    def __init__(self) -> None:
        super().__init__('robot_monitor')
        self.declare_parameter('summary_period', 1.0)
        self.declare_parameter('metrics_flush_period', 5.0)
        self.declare_parameter('summary_log_every_n', 5)
        self.declare_parameter('event_log_path', '/tmp/inspection_robot/events.jsonl')
        self.declare_parameter('event_log_flush_every', 8)
        self.declare_parameter('event_log_rotate_max_bytes', 524288)
        self.declare_parameter('event_log_backup_count', 4)
        self.declare_parameter('event_log_max_pending_records', 256)
        self.declare_parameter('metrics_path', '/tmp/inspection_robot/metrics.json')
        self.declare_parameter('evidence_index_path', '/tmp/inspection_robot/evidence_index.json')
        self.declare_parameter('evidence_index_auto_flush_every', 8)
        self.declare_parameter('diagnostics_enabled', True)
        self.callback_groups = build_callback_groups()
        self.snapshot = StatusSnapshot()
        self.metrics = Metrics()
        self.logger_jsonl = JsonlEventLogger(
            str(self.get_parameter('event_log_path').value),
            auto_flush_every=int(self.get_parameter('event_log_flush_every').value),
            rotate_max_bytes=int(self.get_parameter('event_log_rotate_max_bytes').value),
            backup_count=int(self.get_parameter('event_log_backup_count').value),
            max_pending_records=int(self.get_parameter('event_log_max_pending_records').value),
        )
        self.evidence_index = EvidenceIndex(
            str(self.get_parameter('evidence_index_path').value),
            auto_flush_every=int(self.get_parameter('evidence_index_auto_flush_every').value),
        )
        self.summary_pub = self.create_publisher(String, '/robot/monitor/summary', qos_for('status_summary'))
        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self._summary_publish_count = 0
        self._last_metrics_flush_ns = 0
        self._last_health: str | None = None
        self._runtime_low_power_threshold = 25.0
        diagnostics_enabled = bool(self.get_parameter('diagnostics_enabled').value)
        if diagnostics_enabled and DiagnosticArray is not None:
            self.diagnostics_pub = self.create_publisher(DiagnosticArray, '/diagnostics', qos_for('status_summary'))
            self.diagnostics_json_pub = None
        elif diagnostics_enabled:
            self.diagnostics_pub = None
            self.diagnostics_json_pub = self.create_publisher(String, '/robot/monitor/diagnostics_json', qos_for('status_summary'))
        else:
            self.diagnostics_pub = None
            self.diagnostics_json_pub = None

        call_with_callback_group(self.create_subscription, ModeState, '/robot/mode_state', self.on_mode, qos_for('mode_state'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, SystemStatus, '/robot/system_status', self.on_status, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, ChassisState, '/robot/chassis_state', self.on_chassis, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, PowerState, '/robot/power_state', self.on_power, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, VoiceCommand, '/robot/voice/cmd', self.on_voice, qos_for('perception'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, Fault, '/robot/fault', self.on_fault, qos_for('fault_event'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, EventLog, '/robot/events', self.on_event, qos_for('event_log'), callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_subscription, String, '/robot/vision/qrcode', self.on_qrcode, qos_for('event_log'), callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_subscription, String, '/robot/control/source', self.on_control_source, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/bridge/summary', self.on_bridge_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, RUNTIME_PARAM_TOPIC, self.on_runtime_params, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)


        self.timer = call_with_callback_group(self.create_timer, float(self.get_parameter('summary_period').value), self.publish_summary, callback_group=self.callback_groups.background)
        self.get_logger().info(f'robot_monitor started (diagnostics={diagnostic_transport_type() if diagnostics_enabled else "disabled"})')

    def _log_runtime_io_error(self, scope: str, exc: Exception) -> None:
        self.get_logger().error(f'{scope} failed: {exc}')

    def _safe_evidence_update(self, **fields) -> None:
        try:
            self.evidence_index.update(**fields)
        except Exception as exc:
            self._log_runtime_io_error('evidence index update', exc)

    def _safe_evidence_record_event(self, category: str, name: str, detail: str = '') -> None:
        try:
            self.evidence_index.record_event(category, name, detail)
        except Exception as exc:
            self._log_runtime_io_error('evidence index event append', exc)

    def _safe_evidence_record_snapshot(self, filepath: str) -> None:
        try:
            self.evidence_index.record_snapshot(filepath)
        except Exception as exc:
            self._log_runtime_io_error('evidence index snapshot append', exc)

    def _safe_logger_append(self, record: dict[str, object]) -> None:
        """Append one monitoring event to the JSONL writer with failure containment.

        Args:
            record: Serializable monitoring event record.

        Returns:
            None.

        Raises:
            None. Writer failures are converted into runtime IO errors and counted.

        Boundary behavior:
            The monitoring node must never raise into the upstream event callback because
            event logging is auxiliary evidence collection, not the authoritative event path.
        """
        try:
            self.logger_jsonl.append(record)
            if hasattr(self.metrics, 'event_log_write_successes'):
                self.metrics.event_log_write_successes += 1
        except Exception as exc:
            if hasattr(self.metrics, 'event_log_write_failures'):
                self.metrics.event_log_write_failures += 1
            self._log_runtime_io_error('event log append', exc)

    def on_mode(self, msg: ModeState) -> None:
        self.snapshot.mode = msg.current_mode

    def on_status(self, msg: SystemStatus) -> None:
        self.snapshot.wifi_ok = msg.wifi_ok
        self.snapshot.camera_ok = msg.camera_ok
        self.snapshot.audio_ok = msg.audio_ok
        self.snapshot.uart_ok = msg.uart_ok
        self.snapshot.bridge_ok = msg.wifi_ok and msg.uart_ok
        self.snapshot.battery_voltage = msg.battery_voltage
        self.snapshot.battery_low_warn = bool(getattr(msg, 'low_power_warn', False))
        self.snapshot.battery_low_stop = bool(getattr(msg, 'low_power_stop', False))
        self.snapshot.stale_power = bool(getattr(msg, 'low_power_stop', False))
        self.snapshot.stale_vision = not bool(msg.camera_ok)
        self.snapshot.stale_voice = not bool(msg.audio_ok)
        self.snapshot.readiness, self.snapshot.readiness_reason = derive_readiness(self.snapshot)

    def on_chassis(self, msg: ChassisState) -> None:
        self.snapshot.left_rpm = msg.left_rpm
        self.snapshot.right_rpm = msg.right_rpm
        self.snapshot.stale_chassis = bool(not getattr(msg, 'heartbeat_ok', True) or not getattr(msg, 'comm_ok', True) or getattr(msg, 'driver_fault', False))
        self.snapshot.readiness, self.snapshot.readiness_reason = derive_readiness(self.snapshot)

    def on_power(self, msg: PowerState) -> None:
        self.snapshot.battery_voltage = msg.battery_voltage
        self.snapshot.battery_low_warn = bool(getattr(msg, 'low_power_warn', False))
        self.snapshot.battery_low_stop = bool(getattr(msg, 'low_power_stop', False))
        battery_percent = getattr(msg, 'battery_percent', None)
        try:
            threshold_warn = battery_percent is not None and float(battery_percent) <= float(self._runtime_low_power_threshold)
        except (TypeError, ValueError):
            threshold_warn = False
        if threshold_warn:
            self.snapshot.battery_low_warn = True
        self.snapshot.stale_power = bool(self.snapshot.battery_low_stop)

    def on_runtime_params(self, msg: String) -> None:
        """Apply runtime-parameter thresholds used by monitor readiness logic.

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
            publish_policy_outcome(self, outcome=classify_exception('monitor.runtime_params', exc, code='MONITOR_RUNTIME_PARAMS_INVALID', operator_message='monitor runtime parameter sync failed'), event_pub=self.event_pub)
            return
        try:
            threshold = float(payload['params'].get('lowPowerThreshold', self._runtime_low_power_threshold))
            if not math.isfinite(threshold):
                raise ValueError('lowPowerThreshold must be finite')
        except (TypeError, ValueError) as exc:
            publish_policy_outcome(self, outcome=classify_exception('monitor.runtime_params', exc, code='MONITOR_RUNTIME_PARAMS_INVALID', operator_message='monitor runtime parameter sync failed'), event_pub=self.event_pub)
            return
        self._runtime_low_power_threshold = threshold

    def on_control_source(self, msg: String) -> None:
        self.snapshot.control_source = msg.data

    def on_bridge_summary(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except Exception as exc:
            publish_policy_outcome(self, outcome=classify_exception('monitor.bridge_summary', exc, code='MONITOR_BRIDGE_SUMMARY_INVALID', operator_message='bridge summary parse failed'), event_pub=self.event_pub)
            return
        self.snapshot.bridge_ok = bool(payload.get('connected', False))
        self.snapshot.reconnect_count = int(payload.get('reconnect_count', 0))
        self.snapshot.protocol_errors = int(payload.get('protocol_errors', payload.get('invalid_messages', 0)))
        self.snapshot.stale_bridge = bool(payload.get('stale_link', False) or payload.get('transport_degraded', False) or payload.get('state') in {'stale', 'reconnecting', 'disconnected'})
        self.metrics.reconnect_count = self.snapshot.reconnect_count
        self.metrics.protocol_errors = self.snapshot.protocol_errors
        if payload.get('last_protocol_error'):
            issue = str(payload.get('last_protocol_error'))
            self.snapshot.last_protocol_issue = issue
            self._safe_evidence_update(last_protocol_issue=issue)
        self.snapshot.readiness, self.snapshot.readiness_reason = derive_readiness(self.snapshot)

    def on_voice(self, msg: VoiceCommand) -> None:
        self.snapshot.last_voice_cmd = msg.command
        self.metrics.voice_cmd_seen += 1

    def on_fault(self, msg: Fault) -> None:
        self.snapshot.last_fault = f'{msg.code}:{msg.level}'
        self.metrics.faults_seen += 1
        self._safe_evidence_update(last_fault=self.snapshot.last_fault)
        self._safe_evidence_record_event('fault', msg.code, msg.level)

    def on_qrcode(self, msg: String) -> None:
        self.snapshot.last_qrcode = msg.data
        self.metrics.qrcodes_seen += 1

    def on_event(self, msg: EventLog) -> None:
        self.metrics.events_logged += 1
        event_str = f'{msg.category}:{msg.name}'
        self.snapshot.recent_events.append(event_str)
        if msg.category == 'vision' and msg.name == 'snapshot_saved':
            self.metrics.snapshots_saved += 1
            self.snapshot.snapshot_count += 1
            self._safe_evidence_record_snapshot(msg.detail)
        record = {
            'category': msg.category,
            'name': msg.name,
            'detail': msg.detail,
            'level': msg.level,
            'source': msg.source,
            'stamp_sec': msg.stamp.sec,
            'stamp_nanosec': msg.stamp.nanosec,
        }
        self._safe_logger_append(record)
        self._safe_evidence_record_event(msg.category, msg.name, msg.detail)

    def _maybe_flush_metrics(self, *, health: str) -> None:
        now_ns = self.get_clock().now().nanoseconds
        flush_period_ns = int(float(self.get_parameter('metrics_flush_period').value) * 1e9)
        due_by_period = (now_ns - self._last_metrics_flush_ns) >= flush_period_ns
        health_changed = health != self._last_health
        if not due_by_period and not health_changed:
            return
        metrics_path = str(self.get_parameter('metrics_path').value)
        try:
            self.metrics.dump_json(metrics_path)
        except Exception as exc:
            self._log_runtime_io_error('metrics flush', exc)
            return
        self._safe_evidence_update(metrics_path=metrics_path, health=health)
        self._last_metrics_flush_ns = now_ns
        self._last_health = health

    def destroy_node(self) -> bool:
        try:
            self.logger_jsonl.flush()
        except Exception:
            pass
        try:
            self.evidence_index.flush()
        except Exception:
            pass
        return super().destroy_node()

    def publish_summary(self) -> None:
        self.snapshot.readiness, self.snapshot.readiness_reason = derive_readiness(self.snapshot)
        health = self.metrics.health(self.snapshot)
        self.snapshot.health = health
        summary = render_text(self.snapshot, health=health)
        msg = String()
        msg.data = summary
        self.summary_pub.publish(msg)
        self.metrics.summaries_published += 1
        self._summary_publish_count += 1
        try:
            self.logger_jsonl.flush()
        except Exception:
            pass
        self._maybe_flush_metrics(health=health)
        if self.diagnostics_pub is not None:
            arr = DiagnosticArray()
            arr.status = make_diagnostic_statuses(self.snapshot)
            arr.header.stamp = self.get_clock().now().to_msg()
            self.diagnostics_pub.publish(arr)
        elif self.diagnostics_json_pub is not None:
            diag = String()
            diag.data = make_diagnostic_status(self.snapshot)
            self.diagnostics_json_pub.publish(diag)
        log_every_n = max(1, int(self.get_parameter('summary_log_every_n').value))
        if self._summary_publish_count % log_every_n == 0:
            self.get_logger().info(summary)
        else:
            self.get_logger().debug(summary)



def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = MonitorNode()
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
