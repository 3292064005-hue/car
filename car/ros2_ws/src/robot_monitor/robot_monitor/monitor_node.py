from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

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
from robot_contracts.runtime_param_transport import (
    RUNTIME_PARAM_APPLY_RESULT_TOPIC,
    RUNTIME_PARAM_TOPIC,
    build_runtime_param_apply_result,
    dumps_runtime_param_apply_result,
    loads_runtime_param_payload,
)
from robot_utils.qos_profiles import qos_for
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.error_policy import classify_exception, publish_policy_outcome
from robot_utils.system_replay_bundle import SystemReplayAutoCapture, build_runtime_session_metadata


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
        self.declare_parameter('runtime_supervision_topic', '/robot/runtime/supervision')
        self.declare_parameter('runtime_component_timeout_sec', 3.0)
        self.declare_parameter('runtime_component_degraded_timeout_sec', 1.5)
        self.declare_parameter('runtime_required_components', ['mode_state', 'system_status', 'chassis_state', 'bridge_summary', 'decision_summary', 'control_summary'])
        self.declare_parameter('runtime_supervision_history_limit', 32)
        self.declare_parameter('lifecycle_manager_status_topic', '/robot/lifecycle_manager/status')
        self.declare_parameter('voice_ingress_health_topic', '/robot/voice/ingress_health')
        self.declare_parameter('system_replay_auto_export', True)
        self.declare_parameter('system_replay_bundle_path', '/tmp/inspection_robot/system_replay_bundle.json')
        self.declare_parameter('system_replay_source_name', 'robot-monitor')
        self.declare_parameter('system_replay_export_every_n', 1)
        self.declare_parameter('system_replay_history_limit', 120)
        self.declare_parameter('system_replay_log_limit', 256)
        self.declare_parameter('system_replay_trace_limit', 128)
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
        self.runtime_param_apply_pub = self.create_publisher(String, RUNTIME_PARAM_APPLY_RESULT_TOPIC, qos_for('status_summary'))
        self.runtime_supervision_pub = self.create_publisher(String, str(self.get_parameter('runtime_supervision_topic').value), qos_for('status_summary'))
        self._summary_publish_count = 0
        self._last_metrics_flush_ns = 0
        self._last_health: str | None = None
        self._runtime_low_power_threshold = 25.0
        self._runtime_battery_percent = 0.0
        self._system_replay_auto_export = bool(self.get_parameter('system_replay_auto_export').value)
        self._system_replay_bundle_path = str(self.get_parameter('system_replay_bundle_path').value)
        self._system_replay_source_name = str(self.get_parameter('system_replay_source_name').value or 'robot-monitor')
        self._system_replay_export_every_n = max(1, int(self.get_parameter('system_replay_export_every_n').value))
        self._system_replay_export_tick = 0
        self._runtime_param_state: dict[str, Any] = {'lowPowerThreshold': self._runtime_low_power_threshold}
        self._system_replay = SystemReplayAutoCapture(
            history_limit=int(self.get_parameter('system_replay_history_limit').value),
            log_limit=int(self.get_parameter('system_replay_log_limit').value),
            trace_limit=int(self.get_parameter('system_replay_trace_limit').value),
        )
        self._runtime_startup_ready = False
        self._component_last_seen: dict[str, float] = {}
        self._lifecycle_manager_status: dict[str, Any] | None = None
        self._lifecycle_manager_status_at: float = 0.0
        self._voice_ingress_health: dict[str, Any] | None = None
        self._component_topics = {
            'mode_state': '/robot/mode_state',
            'system_status': '/robot/system_status',
            'chassis_state': '/robot/chassis_state',
            'power_state': '/robot/power_state',
            'bridge_summary': '/robot/bridge/summary',
            'decision_summary': '/robot/decision/summary',
            'control_summary': '/robot/control/summary',
            'navigation_status': '/robot/navigation/status',
            'runtime_params': RUNTIME_PARAM_TOPIC,
            'voice_cmd': '/robot/voice/cmd',
            'voice_ingress_health': str(self.get_parameter('voice_ingress_health_topic').value),
            'fault': '/robot/fault',
            'event': '/robot/events',
            'lifecycle_manager_status': str(self.get_parameter('lifecycle_manager_status_topic').value),
        }
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
        call_with_callback_group(self.create_subscription, String, str(self.get_parameter('voice_ingress_health_topic').value), self.on_voice_ingress_health, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, Fault, '/robot/fault', self.on_fault, qos_for('fault_event'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, EventLog, '/robot/events', self.on_event, qos_for('event_log'), callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_subscription, String, '/robot/vision/qrcode', self.on_qrcode, qos_for('event_log'), callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_subscription, String, '/robot/control/source', self.on_control_source, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/bridge/summary', self.on_bridge_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/decision/summary', self.on_decision_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/control/summary', self.on_control_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/navigation/status', self.on_navigation_status, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, str(self.get_parameter('lifecycle_manager_status_topic').value), self.on_lifecycle_manager_status, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, RUNTIME_PARAM_TOPIC, self.on_runtime_params, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)

        self.timer = call_with_callback_group(self.create_timer, float(self.get_parameter('summary_period').value), self.publish_summary, callback_group=self.callback_groups.background)
        self.get_logger().info(f'robot_monitor started (diagnostics={diagnostic_transport_type() if diagnostics_enabled else "disabled"})')

    @staticmethod
    def _runtime_env_value(key: str, default: str) -> str:
        value = str(os.environ.get(key, '') or '').strip()
        return value or default

    def _system_replay_session_metadata(self) -> dict[str, str]:
        profile_name = MonitorNode._runtime_env_value('ROBOT_EFFECTIVE_PROFILE', 'unknown')
        provider_name = MonitorNode._runtime_env_value('ROBOT_EFFECTIVE_NAVIGATION_PROVIDER', 'simple_nav_provider')
        hardware_role = MonitorNode._runtime_env_value('ROBOT_EFFECTIVE_HARDWARE_SURFACE_ROLE', 'ros_projection_only')
        evidence_class = MonitorNode._runtime_env_value('ROBOT_EFFECTIVE_HARDWARE_EVIDENCE_CLASS', 'host_harness_only')
        session_id = MonitorNode._runtime_env_value('ROBOT_EFFECTIVE_FRONTEND_SESSION_ID', f'{profile_name}-monitor-runtime')
        return build_runtime_session_metadata(
            session_id=session_id,
            profile_name=profile_name,
            provider_name=provider_name,
            hardware_role=hardware_role,
            evidence_class=evidence_class,
        )

    def _system_replay_params_payload(self) -> dict[str, Any]:
        state = getattr(self, '_runtime_param_state', None)
        return dict(state) if isinstance(state, dict) else {'lowPowerThreshold': float(getattr(self, '_runtime_low_power_threshold', 25.0))}

    def _system_replay_topics_payload(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name, topic in self._component_topics.items():
            last_seen = self._component_last_seen.get(name)
            rows.append({
                'component': name,
                'topic': topic,
                'lastSeenAt': self._timestamp_to_iso(last_seen),
                'healthy': last_seen is not None,
            })
        return rows

    def _system_replay_recorder(self) -> SystemReplayAutoCapture | None:
        recorder = getattr(self, '_system_replay', None)
        return recorder if isinstance(recorder, SystemReplayAutoCapture) else None

    def _safe_system_replay_call(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        recorder = MonitorNode._system_replay_recorder(self)
        if recorder is None:
            return
        method = getattr(recorder, method_name, None)
        if method is None:
            return
        try:
            method(*args, **kwargs)
        except Exception as exc:
            self._log_runtime_io_error(f'system replay {method_name}', exc)

    def _append_system_replay_summary_sample(self) -> None:
        MonitorNode._safe_system_replay_call(self, 
            'append_history_sample',
            latency_ms=getattr(self.snapshot, 'average_rtt_ms', 0.0),
            battery_percent=getattr(self, '_runtime_battery_percent', 0.0),
            left_wheel=getattr(self.snapshot, 'left_rpm', 0.0),
            right_wheel=getattr(self.snapshot, 'right_rpm', 0.0),
            frame_drops=getattr(self.snapshot, 'frame_drop_count', 0.0),
            ack_latency_ms=getattr(self.snapshot, 'average_rtt_ms', 0.0),
        )

    def _export_system_replay_bundle(self, *, force: bool = False) -> None:
        if not bool(getattr(self, '_system_replay_auto_export', False)):
            return
        self._system_replay_export_tick += 1
        if not force and self._system_replay_export_tick % self._system_replay_export_every_n != 0:
            return
        try:
            recorder = MonitorNode._system_replay_recorder(self)
            if recorder is None:
                return
            for record in self._system_replay_topics_payload():
                MonitorNode._safe_system_replay_call(self, 'record_topic', record)
            recorder.export_bundle(
                self._system_replay_bundle_path,
                source_name=self._system_replay_source_name,
                session_metadata=self._system_replay_session_metadata(),
                params=self._system_replay_params_payload(),
            )
            self._safe_evidence_update(system_replay_bundle_path=self._system_replay_bundle_path)
        except Exception as exc:
            self._log_runtime_io_error('system replay export', exc)

    @staticmethod
    def _timestamp_to_iso(ts_sec: float | None) -> str | None:
        if ts_sec is None:
            return None
        from datetime import datetime, timezone
        return datetime.fromtimestamp(float(ts_sec), tz=timezone.utc).isoformat().replace('+00:00', 'Z')

    def _now_sec(self) -> float:
        return float(self.get_clock().now().nanoseconds) / 1e9

    def _mark_component_seen(self, name: str) -> None:
        self._component_last_seen[str(name)] = self._now_sec()

    def _log_runtime_io_error(self, scope: str, exc: Exception) -> None:
        self.get_logger().error(f'{scope} failed: {exc}')

    def _runtime_required_components(self) -> tuple[str, ...]:
        """Return required runtime components configured for supervision.

        Args:
            None.

        Returns:
            Ordered tuple of required component identifiers.

        Raises:
            None.
        """
        raw = self.get_parameter('runtime_required_components').value or []
        return tuple(str(item) for item in raw if str(item))

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
        self._mark_component_seen('mode_state')
        self.snapshot.mode = msg.current_mode

    def on_status(self, msg: SystemStatus) -> None:
        self._mark_component_seen('system_status')
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
        self._mark_component_seen('chassis_state')
        self.snapshot.left_rpm = msg.left_rpm
        self.snapshot.right_rpm = msg.right_rpm
        self.snapshot.stale_chassis = bool(not getattr(msg, 'heartbeat_ok', True) or not getattr(msg, 'comm_ok', True) or getattr(msg, 'driver_fault', False))
        self.snapshot.readiness, self.snapshot.readiness_reason = derive_readiness(self.snapshot)

    def on_power(self, msg: PowerState) -> None:
        self._mark_component_seen('power_state')
        self.snapshot.battery_voltage = msg.battery_voltage
        self.snapshot.battery_low_warn = bool(getattr(msg, 'low_power_warn', False))
        self.snapshot.battery_low_stop = bool(getattr(msg, 'low_power_stop', False))
        battery_percent = getattr(msg, 'battery_percent', None)
        try:
            self._runtime_battery_percent = float(battery_percent if battery_percent is not None else 0.0)
        except (TypeError, ValueError):
            self._runtime_battery_percent = 0.0
        try:
            threshold_warn = battery_percent is not None and float(battery_percent) <= float(self._runtime_low_power_threshold)
        except (TypeError, ValueError):
            threshold_warn = False
        if threshold_warn:
            self.snapshot.battery_low_warn = True
        self.snapshot.stale_power = bool(self.snapshot.battery_low_stop)

    def _publish_runtime_param_apply_result(self, payload: dict[str, object]) -> None:
        """Publish one runtime-parameter apply acknowledgement for bridge aggregation.

        Args:
            payload: JSON-serializable apply-result payload.

        Returns:
            None.

        Raises:
            None. Publishing failures are logged and swallowed because monitor
            observability must not crash the node while emitting status telemetry.
        """
        try:
            msg = String()
            msg.data = dumps_runtime_param_apply_result(payload)
            self.runtime_param_apply_pub.publish(msg)
        except Exception as exc:
            try:
                self.get_logger().warning(f'failed to publish monitor runtime parameter apply result error={exc}')
            except Exception:
                pass

    def on_runtime_params(self, msg: String) -> None:
        """Apply runtime-parameter thresholds used by monitor readiness logic.

        Args:
            msg: Runtime-parameter synchronization payload.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            The monitor acknowledges authoritative runtime-parameter transactions
            only after it has accepted the new threshold and refreshed the
            readiness snapshot that operator-facing health derives from. Invalid
            payloads therefore either surface a policy outcome (when the payload
            cannot be parsed at all) or return an explicit negative apply-result
            to the bridge when a tracked transaction can still be identified.
        """
        self._mark_component_seen('runtime_params')
        try:
            payload = loads_runtime_param_payload(msg.data)
        except Exception as exc:
            publish_policy_outcome(self, outcome=classify_exception('monitor.runtime_params', exc, code='MONITOR_RUNTIME_PARAMS_INVALID', operator_message='monitor runtime parameter sync failed'), event_pub=self.event_pub)
            return
        transaction_id = str(payload.get('transaction_id', '') or '')
        version = int(payload.get('runtime_param_version', 0) or 0)
        trace_id = str(payload.get('trace_id', '') or '')
        ts = str(payload.get('ts', '') or '')
        params = payload.get('params', {})
        if not isinstance(params, dict):
            exc = TypeError('params must be an object')
            publish_policy_outcome(self, outcome=classify_exception('monitor.runtime_params', exc, code='MONITOR_RUNTIME_PARAMS_INVALID', operator_message='monitor runtime parameter sync failed'), event_pub=self.event_pub)
            if transaction_id:
                MonitorNode._publish_runtime_param_apply_result(self, build_runtime_param_apply_result(
                    consumer='robot_monitor',
                    transaction_id=transaction_id,
                    runtime_param_version=version,
                    ok=False,
                    message='monitor runtime parameter sync failed: params must be an object',
                    ts=ts,
                    trace_id=trace_id,
                ))
            return
        try:
            current_threshold = float(getattr(self, '_runtime_low_power_threshold', 25.0))
            threshold = float(params.get('lowPowerThreshold', current_threshold))
            if not math.isfinite(threshold):
                raise ValueError('lowPowerThreshold must be finite')
        except (TypeError, ValueError) as exc:
            publish_policy_outcome(self, outcome=classify_exception('monitor.runtime_params', exc, code='MONITOR_RUNTIME_PARAMS_INVALID', operator_message='monitor runtime parameter sync failed'), event_pub=self.event_pub)
            if transaction_id:
                MonitorNode._publish_runtime_param_apply_result(self, build_runtime_param_apply_result(
                    consumer='robot_monitor',
                    transaction_id=transaction_id,
                    runtime_param_version=version,
                    ok=False,
                    message=f'monitor runtime parameter sync failed: {exc}',
                    ts=ts,
                    trace_id=trace_id,
                ))
            return
        self._runtime_low_power_threshold = threshold
        if not isinstance(getattr(self, '_runtime_param_state', None), dict):
            self._runtime_param_state = {}
        self._runtime_param_state['lowPowerThreshold'] = threshold
        self.snapshot.readiness, self.snapshot.readiness_reason = derive_readiness(self.snapshot)
        MonitorNode._safe_system_replay_call(self, 'record_trace', {
            'scope': 'runtime_params',
            'consumer': 'robot_monitor',
            'transactionId': transaction_id,
            'traceId': trace_id,
            'runtimeParamVersion': version,
        })
        MonitorNode._safe_system_replay_call(self, 'record_service_action_event', {
            'kind': 'runtime_param_apply_result',
            'consumer': 'robot_monitor',
            'transactionId': transaction_id,
            'traceId': trace_id,
            'runtimeParamVersion': version,
            'ok': True,
        })
        if transaction_id:
            MonitorNode._publish_runtime_param_apply_result(self, build_runtime_param_apply_result(
                consumer='robot_monitor',
                transaction_id=transaction_id,
                runtime_param_version=version,
                ok=True,
                message='monitor runtime parameters applied',
                ts=ts,
                trace_id=trace_id,
            ))

    def on_control_source(self, msg: String) -> None:
        self.snapshot.control_source = msg.data

    def on_bridge_summary(self, msg: String) -> None:
        self._mark_component_seen('bridge_summary')
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

    def on_decision_summary(self, msg: String) -> None:
        """Mark the decision layer as alive when it publishes one summary update."""
        del msg
        self._mark_component_seen('decision_summary')

    def on_control_summary(self, msg: String) -> None:
        """Mark the control layer as alive when it publishes one summary update."""
        del msg
        self._mark_component_seen('control_summary')

    def on_navigation_status(self, msg: String) -> None:
        """Mark the navigation layer as alive when it publishes one status update."""
        del msg
        self._mark_component_seen('navigation_status')

    def on_voice(self, msg: VoiceCommand) -> None:
        self._mark_component_seen('voice_cmd')
        self.snapshot.last_voice_cmd = msg.command
        self.metrics.voice_cmd_seen += 1

    def on_voice_ingress_health(self, msg: String) -> None:
        """Consume one ASR ingress health snapshot for supervision/reporting.

        Args:
            msg: JSON-encoded voice ingress health payload.

        Returns:
            None.

        Raises:
            None. Malformed payloads are reported and ignored.
        """
        try:
            payload = json.loads(msg.data or '{}')
        except Exception as exc:
            publish_policy_outcome(self, outcome=classify_exception('monitor.voice_ingress_health', exc, code='MONITOR_VOICE_INGRESS_HEALTH_INVALID', operator_message='voice ingress health parse failed'), event_pub=self.event_pub)
            return
        if not isinstance(payload, dict):
            publish_policy_outcome(self, outcome=classify_exception('monitor.voice_ingress_health', TypeError('payload must be an object'), code='MONITOR_VOICE_INGRESS_HEALTH_INVALID', operator_message='voice ingress health parse failed'), event_pub=self.event_pub)
            return
        self._voice_ingress_health = payload
        self.snapshot.voice_ingress_state = str(payload.get('state', 'unknown') or 'unknown')
        self.snapshot.voice_ingress_reason = str(payload.get('reason', 'unknown') or 'unknown')
        self.snapshot.voice_ingress_source = str(payload.get('lastSourceId', payload.get('expectedSourceId', '')) or '')
        self._mark_component_seen('voice_ingress_health')

    def on_fault(self, msg: Fault) -> None:
        self._mark_component_seen('fault')
        self.snapshot.last_fault = f'{msg.code}:{msg.level}'
        self.metrics.faults_seen += 1
        self._safe_evidence_update(last_fault=self.snapshot.last_fault)
        self._safe_evidence_record_event('fault', msg.code, msg.level)

    def on_qrcode(self, msg: String) -> None:
        self.snapshot.last_qrcode = msg.data
        self.metrics.qrcodes_seen += 1

    def on_event(self, msg: EventLog) -> None:
        self._mark_component_seen('event')
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
        MonitorNode._safe_system_replay_call(self, 'record_log', {
            'id': f'{msg.category}:{msg.name}:{msg.stamp.sec}.{msg.stamp.nanosec}',
            'timestamp': self._timestamp_to_iso(float(msg.stamp.sec) + float(msg.stamp.nanosec) / 1e9),
            'level': msg.level,
            'domain': msg.category,
            'message': msg.name,
            'details': msg.detail,
            'source': msg.source,
        })
        self._safe_evidence_record_event(msg.category, msg.name, msg.detail)

    def _runtime_supervision_payload(self) -> dict[str, Any]:
        """Build one runtime-supervision payload covering startup and steady-state health.

        Args:
            None.

        Returns:
            JSON-serialisable runtime-supervision payload with component health,
            reasons, authoritative ROS lifecycle-manager state, bond supervision,
            and the effective recovery mode.

        Raises:
            None.

        Boundary behavior:
            Before all required components have been observed at least once, the
            supervisor reports ``booting`` instead of forcing runtime failures.
            Once startup is complete, missing or stale core summaries escalate to
            ``degraded`` or ``unavailable`` and can therefore drive SAFE_STOP at
            the decision layer. Lifecycle and bond semantics are consumed only
            from the authoritative ROS lifecycle-manager status topic; this
            method no longer synthesizes a parallel repository-local lifecycle
            state machine.
        """
        now_sec = self._now_sec()
        degraded_timeout = max(0.1, float(self.get_parameter('runtime_component_degraded_timeout_sec').value))
        unavailable_timeout = max(degraded_timeout, float(self.get_parameter('runtime_component_timeout_sec').value))
        required = [str(item) for item in (self.get_parameter('runtime_required_components').value or []) if str(item)]
        components: dict[str, Any] = {}
        missing_required: list[str] = []
        degraded_reasons: list[str] = []
        unavailable_reasons: list[str] = []
        all_names = list(dict.fromkeys(required + list(self._component_topics)))
        for name in all_names:
            last_seen = self._component_last_seen.get(name)
            age_sec = None if last_seen is None else max(0.0, now_sec - float(last_seen))
            status = 'ready'
            healthy = True
            stale = False
            bond_state = 'bonded'
            if last_seen is None:
                status = 'missing'
                healthy = False
                stale = True
                bond_state = 'awaiting'
                if name in required:
                    missing_required.append(name)
            elif age_sec >= unavailable_timeout:
                status = 'unavailable'
                healthy = False
                stale = True
                bond_state = 'broken'
                if name in required:
                    unavailable_reasons.append(f'{name}_timeout')
            elif age_sec >= degraded_timeout:
                status = 'degraded'
                healthy = False
                stale = True
                bond_state = 'stale'
                if name in required:
                    degraded_reasons.append(f'{name}_stale')
            components[name] = {
                'status': status,
                'healthy': healthy,
                'stale': stale,
                'required': name in required,
                'ageSec': None if age_sec is None else round(float(age_sec), 3),
                'lastSeenAt': self._timestamp_to_iso(last_seen),
                'topic': self._component_topics.get(name),
                'bondState': bond_state if name in required else None,
            }

        readiness, readiness_reason = derive_readiness(self.snapshot)
        startup_ready = not missing_required
        self._runtime_startup_ready = bool(self._runtime_startup_ready or startup_ready)
        reasons: list[str] = []
        state = 'ready'
        if not self._runtime_startup_ready:
            state = 'booting'
            reasons.extend(f'{name}_awaiting_first_sample' for name in missing_required)
        else:
            if self.snapshot.last_fault.endswith(':fatal'):
                state = 'faulted'
                reasons.append('fatal_fault')
            elif self.snapshot.battery_low_stop:
                state = 'faulted'
                reasons.append('battery_critical')
            elif unavailable_reasons or readiness == 'blocked':
                state = 'unavailable'
                reasons.extend(unavailable_reasons)
                if readiness == 'blocked' and readiness_reason:
                    reasons.append(f'readiness_{readiness_reason}')
            elif degraded_reasons or readiness == 'degraded' or self.snapshot.protocol_errors > 0:
                state = 'degraded'
                reasons.extend(degraded_reasons)
                if readiness == 'degraded' and readiness_reason:
                    reasons.append(f'readiness_{readiness_reason}')
                if self.snapshot.protocol_errors > 0:
                    reasons.append('protocol_errors')
        lifecycle_status_payload = self._lifecycle_manager_status if isinstance(self._lifecycle_manager_status, dict) else {}
        lifecycle_snapshot = lifecycle_status_payload.get('lifecycleManager', {}) if isinstance(lifecycle_status_payload.get('lifecycleManager', {}), dict) else {}
        bond_snapshot = lifecycle_status_payload.get('bondSupervision', {}) if isinstance(lifecycle_status_payload.get('bondSupervision', {}), dict) else {}
        recovery_plan = lifecycle_status_payload.get('recoveryPlan', {}) if isinstance(lifecycle_status_payload.get('recoveryPlan', {}), dict) else {}
        lifecycle_present = bool(lifecycle_snapshot.get('present'))
        lifecycle_ready = bool(lifecycle_status_payload.get('ready')) if lifecycle_status_payload else False
        lifecycle_state = str(lifecycle_snapshot.get('state', '') or '').strip().lower()
        bond_state = str(bond_snapshot.get('state', '') or '').strip().lower()
        lifecycle_status_age_sec = None
        if self._lifecycle_manager_status_at > 0.0:
            lifecycle_status_age_sec = max(0.0, now_sec - float(self._lifecycle_manager_status_at))
        lifecycle_status_stale = lifecycle_status_age_sec is None or lifecycle_status_age_sec >= unavailable_timeout
        if self._runtime_startup_ready and lifecycle_status_stale:
            if state not in {'faulted', 'unavailable'}:
                state = 'unavailable'
            reasons.append('ros_lifecycle_manager_status_stale')
            lifecycle_snapshot = {
                'present': False,
                'type': 'ros_lifecycle_manager',
                'state': 'unavailable',
                'lastUpdateAgeSec': None if lifecycle_status_age_sec is None else round(float(lifecycle_status_age_sec), 3),
            }
            bond_snapshot = {
                'present': False,
                'type': 'bondpy_supervision',
                'state': 'unavailable',
                'lastUpdateAgeSec': None if lifecycle_status_age_sec is None else round(float(lifecycle_status_age_sec), 3),
            }
            recovery_plan = {
                'strategy': 'inspect_ros_lifecycle_manager',
                'reason': 'ros_lifecycle_manager_status_stale',
                'lastUpdateAgeSec': None if lifecycle_status_age_sec is None else round(float(lifecycle_status_age_sec), 3),
            }
            lifecycle_present = False
            lifecycle_ready = False
        elif self._runtime_startup_ready and not lifecycle_present:
            if state == 'ready':
                state = 'degraded'
            reasons.append('ros_lifecycle_manager_unavailable')
            lifecycle_snapshot = {'present': False, 'type': 'ros_lifecycle_manager', 'state': 'unavailable'}
            bond_snapshot = {'present': False, 'type': 'bondpy_supervision', 'state': 'unavailable'}
            recovery_plan = {'strategy': 'inspect_ros_lifecycle_manager', 'reason': 'ros_lifecycle_manager_unavailable'}
        elif lifecycle_present:
            if lifecycle_state in {'error', 'inactive', 'unconfigured'} or bond_state == 'broken':
                if state not in {'faulted', 'unavailable'}:
                    state = 'unavailable'
                reasons.append('ros_lifecycle_manager_not_active')
            elif not lifecycle_ready or lifecycle_state != 'active' or bond_state not in {'bonded', 'disabled'}:
                if state == 'ready':
                    state = 'degraded'
                reasons.append('ros_lifecycle_manager_degraded')
        if not reasons and state == 'ready':
            reasons.append('all_core_components_fresh')
        elif state != 'ready':
            reasons = [reason for reason in reasons if reason != 'all_core_components_fresh']

        voice_ingress_health = getattr(self, '_voice_ingress_health', None)
        payload = {
            'state': state,
            'reasons': list(dict.fromkeys(reasons)),
            'components': components,
            'voiceIngressHealth': voice_ingress_health if isinstance(voice_ingress_health, dict) else None,
            'startupBarrierReady': bool(getattr(self, '_runtime_startup_ready', False)),
            'startupBarrierPending': [name for name in required if components.get(name, {}).get('status') == 'missing'],
            'readiness': readiness,
            'readinessReason': readiness_reason,
            'recoveryMode': 'safe_stop_or_process_supervised' if state in {'faulted', 'unavailable'} else 'observe_and_recover',
            'lifecycleManager': lifecycle_snapshot,
            'bondSupervision': bond_snapshot,
            'recoveryPlan': recovery_plan,
            'ts': self._timestamp_to_iso(now_sec),
        }
        MonitorNode._safe_system_replay_call(self, 'record_inspector_trace', payload)
        self._safe_evidence_update(runtime_supervision=payload)
        return payload

    def _publish_runtime_supervision(self) -> dict[str, Any]:
        payload = self._runtime_supervision_payload()
        try:
            msg = String()
            msg.data = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
            self.runtime_supervision_pub.publish(msg)
        except Exception as exc:
            self._log_runtime_io_error('runtime supervision publish', exc)
        return payload


    def on_lifecycle_manager_status(self, msg: String) -> None:
        """Cache the latest ROS lifecycle-manager status snapshot.

        Args:
            msg: JSON-encoded lifecycle-manager status payload.

        Returns:
            None.

        Raises:
            None. Invalid payloads are reported and ignored.
        """
        try:
            payload = json.loads(msg.data or '{}')
        except Exception as exc:
            publish_policy_outcome(self, outcome=classify_exception('monitor.lifecycle_manager_status', exc, code='MONITOR_LIFECYCLE_STATUS_INVALID', operator_message='monitor lifecycle-manager status parse failed'), event_pub=self.event_pub)
            return
        if not isinstance(payload, dict):
            publish_policy_outcome(self, outcome=classify_exception('monitor.lifecycle_manager_status', TypeError('payload must be an object'), code='MONITOR_LIFECYCLE_STATUS_INVALID', operator_message='monitor lifecycle-manager status parse failed'), event_pub=self.event_pub)
            return
        self._lifecycle_manager_status = payload
        self._lifecycle_manager_status_at = self._now_sec()
        self._mark_component_seen('lifecycle_manager_status')

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
            self._export_system_replay_bundle(force=True)
        except Exception:
            pass
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
        runtime_supervision = self._publish_runtime_supervision()
        self.metrics.summaries_published += 1
        self._summary_publish_count += 1
        try:
            self.logger_jsonl.flush()
        except Exception:
            pass
        self._append_system_replay_summary_sample()
        self._export_system_replay_bundle()
        self._maybe_flush_metrics(health=health)
        if self.diagnostics_pub is not None:
            arr = DiagnosticArray()
            arr.status = make_diagnostic_statuses(self.snapshot)
            arr.header.stamp = self.get_clock().now().to_msg()
            self.diagnostics_pub.publish(arr)
        elif self.diagnostics_json_pub is not None:
            diag = String()
            diag_payload = {
                'summary': make_diagnostic_status(self.snapshot),
                'runtimeSupervision': runtime_supervision,
            }
            diag.data = json.dumps(diag_payload, ensure_ascii=False, separators=(',', ':'))
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
