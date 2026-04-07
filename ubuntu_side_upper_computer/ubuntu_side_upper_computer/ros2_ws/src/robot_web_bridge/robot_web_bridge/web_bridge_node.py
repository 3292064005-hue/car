from __future__ import annotations

import json
from typing import Any, Mapping

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

try:
    from rclpy.executors import MultiThreadedExecutor
except Exception:  # pragma: no cover - lightweight test stubs may omit executors
    MultiThreadedExecutor = None
from std_msgs.msg import String

from robot_contracts.bridge_contract import (
    CommandContext,
    RuntimeParameterTransaction,
    command_capability_snapshot,
)
from robot_msgs.msg import ChassisState, EventLog, Fault, ModeState, PowerState, SpeakRequest, SystemStatus, VisionTarget, VoiceCommand
from robot_msgs.srv import ResetFault, SaveSnapshot, SetMode
from robot_contracts.runtime_param_transport import (
    RUNTIME_PARAM_APPLY_RESULT_TOPIC,
    RUNTIME_PARAM_TOPIC,
)

from robot_utils.qos_profiles import qos_for
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.error_policy import classify_exception, publish_policy_outcome
from .command_router import CommandRouter
from .components.command_dispatcher import CommandDispatcher
from .components.snapshot_cache import SnapshotCache
from .components.readiness_cache import ReadinessCache
from .components.web_gateway import WebGateway
from .components.state_projector import StateProjector
from .components.state_store import StateStore
from .components.command_lifecycle import CommandLifecycleTracker
from .components.ingress_service import IngressService
from .components.runtime_param_coordinator import RuntimeParamCoordinator
from .envelope import EnvelopeFactory, build_connection_payload
from .payload_budget import (
    DEFAULT_CONTROL_PAYLOAD_BUDGET_BYTES,
    DEFAULT_SNAPSHOT_PAYLOAD_BUDGET_BYTES,
    DEFAULT_TELEMETRY_PAYLOAD_BUDGET_BYTES,
)
from .state_model import WebBridgeState


class RobotWebBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__('robot_web_bridge')
        self.declare_parameter('listen_host', '0.0.0.0')
        self.declare_parameter('listen_port', 9001)
        self.declare_parameter('ws_path', '/ws')
        self.declare_parameter('mjpeg_url', '')
        self.declare_parameter('heartbeat_period', 1.0)
        self.declare_parameter('readiness_refresh_period', 1.0)
        self.declare_parameter('telemetry_payload_budget_bytes', DEFAULT_TELEMETRY_PAYLOAD_BUDGET_BYTES)
        self.declare_parameter('control_payload_budget_bytes', DEFAULT_CONTROL_PAYLOAD_BUDGET_BYTES)
        self.declare_parameter('snapshot_payload_budget_bytes', DEFAULT_SNAPSHOT_PAYLOAD_BUDGET_BYTES)
        self.declare_parameter('ingress_queue_max', 128)
        self.declare_parameter('dispatch_batch_max', 8)
        self.declare_parameter('dispatch_reserved_high_priority_slots', 2)
        self.declare_parameter('command_future_timeout_sec', 10.0)
        self.declare_parameter('teleop_latest_only', True)
        self.declare_parameter('ingress_drop_policy', 'reject')
        self.declare_parameter('runtime_param_apply_timeout_sec', 3.0)

        self.callback_groups = build_callback_groups()
        self.state = WebBridgeState()
        self.state_store = StateStore(state=self.state, snapshot_sync=self._sync_snapshot_cache)
        self.envelopes = EnvelopeFactory(session_id='robot-web-bridge')

        self.manual_pub = self.create_publisher(Twist, '/robot/manual/cmd_vel', qos_for('control_cmd'))
        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self.speak_pub = self.create_publisher(SpeakRequest, '/robot/speak_req', qos_for('control_cmd'))
        self.runtime_param_pub = self.create_publisher(String, RUNTIME_PARAM_TOPIC, qos_for('status_summary'))
        self.runtime_param_apply_result_sub = self.create_subscription(String, RUNTIME_PARAM_APPLY_RESULT_TOPIC, self.on_runtime_param_apply_result, qos_for('status_summary'))
        self.mode_client = self.create_client(SetMode, '/robot/set_mode')
        self.reset_client = self.create_client(ResetFault, '/robot/reset_fault')
        self.snapshot_client = self.create_client(SaveSnapshot, '/robot/save_snapshot')
        self.command_router = CommandRouter(self, operation_timeout_sec=float(self.get_parameter('command_future_timeout_sec').value))
        self.command_lifecycle = CommandLifecycleTracker(store=self.state_store, now_iso=self.now_iso)
        self.runtime_param_coordinator = RuntimeParamCoordinator(node=self)
        self.ingress_service = IngressService(node=self)
        self.readiness_cache = ReadinessCache(
            checks={
                '/robot/set_mode': lambda timeout_sec: self.mode_client.wait_for_service(timeout_sec=timeout_sec),
                '/robot/reset_fault': lambda timeout_sec: self.reset_client.wait_for_service(timeout_sec=timeout_sec),
                '/robot/save_snapshot': lambda timeout_sec: self.snapshot_client.wait_for_service(timeout_sec=timeout_sec),
                '/robot/actions/start_patrol': lambda timeout_sec: bool(self.command_router.patrol_action_client and self.command_router.patrol_action_client.wait_for_server(timeout_sec=timeout_sec)),
                '/robot/actions/track_target': lambda timeout_sec: bool(self.command_router.track_action_client and self.command_router.track_action_client.wait_for_server(timeout_sec=timeout_sec)),
                '/robot/actions/save_snapshot': lambda timeout_sec: bool(self.command_router.snapshot_action_client and self.command_router.snapshot_action_client.wait_for_server(timeout_sec=timeout_sec)),
            },
            logger=self.get_logger(),
        )
        self.dispatcher = CommandDispatcher(
            router_handle=self.ingress_service.dispatch_command,
            ack_sender=self.send_ack,
            logger=self.get_logger(),
            max_queue_size=int(self.get_parameter('ingress_queue_max').value),
            reserved_high_priority_slots=int(self.get_parameter('dispatch_reserved_high_priority_slots').value),
            latest_only_types=('teleop_cmd',) if bool(self.get_parameter('teleop_latest_only').value) else (),
            stats_callback=self.on_dispatcher_observation,
            failure_callback=self.ingress_service.on_dispatch_failure,
        )
        self.state_projector = StateProjector(node=self)

        call_with_callback_group(self.create_subscription, ModeState, '/robot/mode_state', self.on_mode_state, qos_for('mode_state'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, ChassisState, '/robot/chassis_state', self.on_chassis_state, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, PowerState, '/robot/power_state', self.on_power_state, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, VisionTarget, '/robot/vision/target', self.on_vision_target, qos_for('perception'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/vision/qrcode', self.on_qrcode, qos_for('event_log'), callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_subscription, VoiceCommand, '/robot/voice/cmd', self.on_voice_cmd, qos_for('perception'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, Fault, '/robot/fault', self.on_fault, qos_for('fault_event'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, EventLog, '/robot/events', self.on_event_log, qos_for('event_log'), callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_subscription, SystemStatus, '/robot/system_status', self.on_system_status, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/bridge/summary', self.on_bridge_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/bridge/transport_stats', self.on_transport_stats, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/decision/summary', self.on_decision_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)

        self.heartbeat_timer = call_with_callback_group(self.create_timer, float(self.get_parameter('heartbeat_period').value), self.publish_heartbeat, callback_group=self.callback_groups.background)
        self.command_timer = call_with_callback_group(self.create_timer, 0.05, self.process_command_queue, callback_group=self.callback_groups.control)
        self.readiness_timer = call_with_callback_group(self.create_timer, float(self.get_parameter('readiness_refresh_period').value), self.refresh_readiness, callback_group=self.callback_groups.background)

        self.snapshot_cache = SnapshotCache(builder=self._build_snapshot_envelope)
        self.gateway = WebGateway(
            host=str(self.get_parameter('listen_host').value),
            port=int(self.get_parameter('listen_port').value),
            ws_path=str(self.get_parameter('ws_path').value),
            snapshot_provider=self.get_cached_snapshot_envelope,
            command_handler=self.ingress_service.handle_ws_message,
            stats_callback=self.on_transport_observation,
            telemetry_payload_budget_bytes=int(self.get_parameter('telemetry_payload_budget_bytes').value),
            control_payload_budget_bytes=int(self.get_parameter('control_payload_budget_bytes').value),
            snapshot_payload_budget_bytes=int(self.get_parameter('snapshot_payload_budget_bytes').value),
        )
        self._refresh_contract_snapshot()
        self.refresh_readiness()
        self._sync_dispatcher_snapshot()
        self._sync_snapshot_cache()
        self.gateway.start()
        host = str(self.get_parameter('listen_host').value)
        port = int(self.get_parameter('listen_port').value)
        path = str(self.get_parameter('ws_path').value)
        self.get_logger().info(f'robot_web_bridge listening on ws://{host}:{port}{path}')

    def now_iso(self) -> str:
        from robot_contracts.bridge_contract import now_iso
        return now_iso()

    def connection_payload(self) -> dict[str, Any]:
        return build_connection_payload(self.state)

    def build_command_context(self) -> CommandContext:
        """Project current web-bridge state into the shared command contract context.

        Args:
            None.

        Returns:
            ``CommandContext`` snapshot.

        Raises:
            None.
        """
        fault_level = str(self.state.fault.get('level', 'info') or 'info').lower()
        return CommandContext(
            current_mode=self.state.mode,
            bridge_connected=bool((self.state.transport_stats or self.state.bridge_summary).get('connected', self.state.bridge_summary.get('connected', False)) or self.state.system_status.get('wifi_ok', False)),
            low_power_warning=bool(self.state.power.get('lowPowerWarning', False) or self.state.system_status.get('low_power_warn', False) or self.state.system_status.get('low_power_stop', False)),
            fault_code=self.state.fault.get('code'),
            fault_level='critical' if fault_level in {'critical', 'fatal', 'error'} else 'warning' if fault_level in {'warning', 'warn'} else 'info',
            estop_active=bool(self.state.fault.get('estopActive', False)),
            safe_stop_active=bool(self.state.fault.get('safeStopActive', False)),
            safe_stop_recoverable=bool(self.state.contract_snapshot.get('safeStopRecoverable', self.state.fault.get('recoverable', True))),
            safe_stop_requires_manual_ack=bool(self.state.contract_snapshot.get('safeStopRequiresManualAck', False)),
            safe_stop_blocked_reason=self.state.contract_snapshot.get('safeStopBlockedReason'),
        )

    def _refresh_contract_snapshot(self, summary_data: Mapping[str, Any] | None = None) -> None:
        """Refresh the frontend-facing command capability snapshot.

        Args:
            summary_data: Optional authoritative decision summary override.

        Returns:
            None.

        Raises:
            None.
        """
        if isinstance(summary_data, Mapping) and 'command_permissions' in summary_data:
            authoritative_mode = str(summary_data.get('mode', self.state.mode) or self.state.mode)
            self.state.contract_snapshot = {
                'allowedTargetModes': list(summary_data.get('allowed_target_modes', [])),
                'modeReasons': dict(summary_data.get('mode_reasons', {})),
                'commandPermissions': dict(summary_data.get('command_permissions', {})),
                'safeStopRecoverable': bool(summary_data.get('safe_stop_recoverable', True)),
                'safeStopRequiresManualAck': bool(summary_data.get('safe_stop_requires_manual_ack', False)),
                'safeStopBlockedReason': summary_data.get('safe_stop_blocked_reason'),
            }
            self.state.contract_snapshot_authoritative = True
            self.state.contract_snapshot_mode = authoritative_mode
            return
        if self.state.contract_snapshot_authoritative and self.state.contract_snapshot_mode == self.state.mode:
            return
        self.state.contract_snapshot = command_capability_snapshot(self.build_command_context())
        self.state.contract_snapshot_authoritative = False
        self.state.contract_snapshot_mode = self.state.mode

    def _sync_snapshot_cache(self) -> None:
        self.snapshot_cache.refresh()

    def _build_snapshot_envelope(self) -> dict[str, Any]:
        return self.envelopes.event('snapshot', self.state.snapshot(mjpeg_url=str(self.get_parameter('mjpeg_url').value), connection=self.connection_payload()))

    def get_cached_snapshot_envelope(self) -> dict[str, Any]:
        return self.snapshot_cache.get()

    def broadcast_snapshot(self) -> None:
        self._sync_snapshot_cache()
        self.schedule_send(self.get_cached_snapshot_envelope())

    @staticmethod
    def _mutate_state_compat(instance: Any, callback: Callable[[Any], None]) -> None:
        """Apply one state mutation for both full runtime nodes and lightweight test doubles.

        Args:
            instance: Bridge node or test double carrying bridge state.
            callback: Mutation callback operating on ``instance.state``.

        Returns:
            None.

        Raises:
            None.
        """
        store = getattr(instance, 'state_store', None)
        if store is not None:
            store.mutate(callback)
            return
        callback(instance.state)
        sync = getattr(instance, '_sync_snapshot_cache', None)
        if callable(sync):
            sync()

    @staticmethod
    def _record_trace_id_compat(instance: Any, trace_id: str) -> None:
        """Persist one trace identifier across full runtime nodes and test doubles.

        Args:
            instance: Bridge node or compatible test double.
            trace_id: Correlation identifier to persist when present.

        Returns:
            None.

        Raises:
            None.
        """
        if not trace_id:
            return
        store = getattr(instance, 'state_store', None)
        if store is not None:
            store.record_trace_id(trace_id)
            return
        state = getattr(instance, 'state', None)
        if state is not None:
            setattr(state, 'last_trace_id', trace_id)
        sync = getattr(instance, '_sync_snapshot_cache', None)
        if callable(sync):
            sync()

    @staticmethod
    def _record_command_phase_compat(
        instance: Any,
        event_id: str,
        command_type: str,
        phase: str,
        status: str,
        message: str,
        *,
        trace_id: str = '',
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        """Record one lifecycle phase when the runtime exposes lifecycle tracking.

        Args:
            instance: Bridge node or test double.
            event_id: Source command identifier.
            command_type: Logical command type.
            phase: Lifecycle phase label.
            status: Lifecycle status label.
            message: Human-readable lifecycle detail.
            trace_id: Optional correlation identifier.
            extra: Optional structured metadata.

        Returns:
            None.

        Raises:
            None.
        """
        if hasattr(instance, 'record_command_phase'):
            instance.record_command_phase(event_id, command_type, phase, status, message, trace_id=trace_id, extra=extra)
            return
        RobotWebBridgeNode._record_trace_id_compat(instance, trace_id)
        timeline = getattr(getattr(instance, 'state', None), 'command_timeline', None)
        if timeline is None:
            return
        item = {
            'commandId': event_id,
            'commandType': command_type,
            'phase': phase,
            'status': status,
            'message': message,
            'traceId': trace_id or None,
            'ts': instance.now_iso() if hasattr(instance, 'now_iso') else '',
        }
        if extra:
            item.update(dict(extra))
        timeline.appendleft(item)
        sync = getattr(instance, '_sync_snapshot_cache', None)
        if callable(sync):
            sync()

    def _ingress_service(self) -> IngressService:
        service = getattr(self, 'ingress_service', None)
        if service is None:
            service = IngressService(node=self)
            try:
                self.ingress_service = service
            except Exception:
                pass
        return service

    def _runtime_param_coordinator(self) -> RuntimeParamCoordinator:
        coordinator = getattr(self, 'runtime_param_coordinator', None)
        if coordinator is None:
            coordinator = RuntimeParamCoordinator(node=self)
            try:
                self.runtime_param_coordinator = coordinator
            except Exception:
                pass
        return coordinator

    def _begin_runtime_param_transaction(self, *, reason: str, trace_id: str = '') -> RuntimeParameterTransaction:
        return RobotWebBridgeNode._runtime_param_coordinator(self).begin_transaction(reason=reason, trace_id=trace_id)

    def _finalize_runtime_param_transaction(self, *, state_label: str, message: str, ok: bool, trace_id: str = '') -> None:
        RobotWebBridgeNode._runtime_param_coordinator(self).finalize_transaction(state_label=state_label, message=message, ok=ok, trace_id=trace_id)

    def _consume_runtime_param_apply_result(self, payload: Mapping[str, Any]) -> None:
        RobotWebBridgeNode._runtime_param_coordinator(self).consume_apply_result(payload)

    def on_runtime_param_apply_result(self, msg: String) -> None:
        """Aggregate consumer runtime-parameter apply acknowledgements."""
        RobotWebBridgeNode._runtime_param_coordinator(self).on_apply_result_message(msg)

    def _expire_runtime_param_transaction(self) -> None:
        RobotWebBridgeNode._runtime_param_coordinator(self).expire_transaction()

    def apply_runtime_param_update(self, *, key: str, value: Any, reason: str, trace_id: str = '') -> str:
        """Apply one bridge-managed runtime parameter mutation."""
        del reason
        return RobotWebBridgeNode._runtime_param_coordinator(self).apply_update(key=key, value=value, trace_id=trace_id)

    def apply_runtime_param_profile(self, *, profile_name: str, reason: str, trace_id: str = '') -> str:
        """Apply one predefined runtime parameter profile."""
        del reason
        return RobotWebBridgeNode._runtime_param_coordinator(self).apply_profile(profile_name=profile_name, trace_id=trace_id)

    def _match_runtime_profile_name(self, params: Mapping[str, Any]) -> str:
        return RobotWebBridgeNode._runtime_param_coordinator(self).match_profile_name(params)

    def _runtime_low_power_threshold(self) -> float:
        """Return the currently effective runtime low-power threshold."""
        return RobotWebBridgeNode._runtime_param_coordinator(self).runtime_low_power_threshold()

    def _publish_runtime_params(self, *, reason: str, trace_id: str = '') -> None:
        """Publish the effective runtime-parameter state to backend consumers."""
        RobotWebBridgeNode._runtime_param_coordinator(self).publish_runtime_params(reason=reason, trace_id=trace_id)

    def refresh_stale_flags(self) -> None:
        transport = self.state.transport_stats or self.state.bridge_summary
        system_status = self.state.system_status or {}
        motion = self.state.motion or {}
        voice = self.state.voice or {}
        battery_percent = self.state.power.get('batteryPercent')
        threshold = self._runtime_low_power_threshold()
        low_power_from_threshold = False
        try:
            if battery_percent is not None:
                low_power_from_threshold = float(battery_percent) <= threshold
        except (TypeError, ValueError):
            low_power_from_threshold = False
        self.state.stale_flags.update({
            'bridge': bool(transport.get('stale_link', False) or transport.get('state') in {'stale', 'reconnecting', 'disconnected'}),
            'transport': bool(transport.get('transport_degraded', False) or transport.get('state') in {'stale', 'reconnecting', 'disconnected'}),
            'vision': bool(not system_status.get('camera_ok', True)),
            'voice': bool(not system_status.get('audio_ok', True)),
            'power': bool(system_status.get('low_power_warn', False) or system_status.get('low_power_stop', False) or low_power_from_threshold),
            'chassis': bool(not system_status.get('uart_ok', True) or not motion.get('heartbeatOk', True) or self.state.fault.get('timeoutStopActive', False)),
        })
        voice_conf = float(voice.get('voiceConfidence', 1.0) or 0.0)
        if self.state.voice and voice.get('lastVoiceCommand') and voice_conf < 0.45:
            self.state.stale_flags['voice'] = True
        self._refresh_contract_snapshot()

    async def handle_ws_message(self, raw: str) -> None:
        await RobotWebBridgeNode._ingress_service(self).handle_ws_message(raw)

    def record_command_phase(self, event_id: str, command_type: str, phase: str, status: str, message: str, *, trace_id: str = '', extra: Mapping[str, Any] | None = None) -> None:
        """Record one normalized command lifecycle event.

        Args:
            event_id: Source command identifier.
            command_type: Logical command type.
            phase: Stable lifecycle phase.
            status: Stable command status.
            message: Human-readable lifecycle detail.
            trace_id: Optional correlation identifier.
            extra: Optional structured metadata.

        Returns:
            None.

        Raises:
            None.
        """
        self.command_lifecycle.record(command_id=event_id, command_type=command_type, phase=phase, status=status, message=message, trace_id=trace_id, extra=extra)

    def dispatch_command(self, cmd: dict[str, Any]) -> None:
        RobotWebBridgeNode._ingress_service(self).dispatch_command(cmd)

    def on_dispatch_failure(self, cmd: dict[str, Any], exc: Exception) -> None:
        RobotWebBridgeNode._ingress_service(self).on_dispatch_failure(cmd, exc)

    def schedule_send(self, envelope: dict[str, Any]) -> None:
        """Emit one envelope through the websocket gateway.

        Args:
            envelope: Already-serialized outbound envelope.

        Returns:
            None.

        Raises:
            None.
        """
        trace_id = str(envelope.get('traceId', '') or '')
        self.state_store.record_trace_id(trace_id)
        self.gateway.schedule_send(envelope)

    def send_ack(
        self,
        command_id: str,
        status: str,
        message: str,
        *,
        detail: str = '',
        trace_id: str = '',
        lifecycle_status: str = '',
    ) -> None:
        """Send one command acknowledgement envelope.

        Args:
            command_id: Source command identifier.
            status: Legacy-compatible acknowledgement status label.
            message: Human-readable operator message.
            detail: Optional machine-friendly detail string.
            trace_id: Optional end-to-end correlation identifier.
            lifecycle_status: Optional precise lifecycle status exposed for
                operator-facing consumers that distinguish acceptance from
                application/completion.

        Returns:
            None.

        Raises:
            None.
        """
        self.state_store.record_trace_id(trace_id)
        self.schedule_send(
            self.envelopes.ack(
                command_id,
                status,
                message,
                detail=detail,
                trace_id=trace_id or None,
                lifecycle_status=lifecycle_status or None,
            )
        )

    def audit_command(self, event_id: str, command_type: str, status: str, message: str) -> None:
        """Append one command audit item into the read model.

        Args:
            event_id: Source command identifier.
            command_type: Logical command type.
            status: Operator-visible command status.
            message: Human-readable audit message.

        Returns:
            None.

        Raises:
            None.
        """
        self.state_store.append_left('command_audit', {
            'id': event_id,
            'ts': self.now_iso(),
            'commandType': command_type,
            'status': status,
            'message': message,
        })


    def on_mode_state(self, msg: ModeState) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_mode_state(msg)

    def on_chassis_state(self, msg: ChassisState) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_chassis_state(msg)

    def on_power_state(self, msg: PowerState) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_power_state(msg)

    def on_vision_target(self, msg: VisionTarget) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_vision_target(msg)

    def on_qrcode(self, msg: String) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_qrcode(msg)

    def on_voice_cmd(self, msg: VoiceCommand) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_voice_cmd(msg)

    def on_fault(self, msg: Fault) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_fault(msg)

    def on_event_log(self, msg: EventLog) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_event_log(msg)

    def on_system_status(self, msg: SystemStatus) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_system_status(msg)

    def on_bridge_summary(self, msg: String) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_bridge_summary(msg)

    def on_transport_stats(self, msg: String) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_transport_stats(msg)

    def on_decision_summary(self, msg: String) -> None:
        getattr(self, 'state_projector', StateProjector(node=self)).on_decision_summary(msg)

    def refresh_readiness(self) -> None:
        """Refresh cached service/action readiness outside the command path.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        snapshot = self.readiness_cache.refresh_all(timeout_sec=0.0)
        current = dict(self.state.transport_stats)
        current['dependencyReadiness'] = snapshot
        self.state_store.replace_mapping('transport_stats', current)

    def on_transport_observation(self, kind: str, **payload: Any) -> None:
        """Accumulate websocket transport observations for diagnostics.

        Args:
            kind: Observation kind.
            **payload: Optional observation fields.

        Returns:
            None.

        Raises:
            None.
        """
        stats = dict(self.state.transport_stats)
        counters = {
            'queue_full': 'queue_full_count',
            'enqueue_failed': 'enqueue_failed_count',
            'client_dropped': 'client_drop_count',
            'client_cleanup_failed': 'client_cleanup_failed_count',
            'future_exception': 'future_exception_count',
            'client_connected': 'client_connected_count',
            'payload_budget_exceeded': 'payload_budget_exceeded_count',
        }
        key = counters.get(kind)
        if key is not None:
            stats[key] = int(stats.get(key, 0) or 0) + 1
        if 'payload_bytes' in payload:
            payload_bytes = int(payload.get('payload_bytes', 0) or 0)
            stats['last_payload_bytes'] = payload_bytes
            stats['payload_bytes_total'] = int(stats.get('payload_bytes_total', 0) or 0) + payload_bytes
            lane = str(payload.get('lane', '') or 'unknown')
            lane_totals = dict(stats.get('payload_bytes_by_lane', {})) if isinstance(stats.get('payload_bytes_by_lane', {}), dict) else {}
            lane_totals[lane] = int(lane_totals.get(lane, 0) or 0) + payload_bytes
            stats['payload_bytes_by_lane'] = lane_totals
            if kind == 'payload_budget_exceeded':
                stats['last_budget_exceeded'] = {
                    'event_type': str(payload.get('event_type', '') or 'telemetry'),
                    'lane': lane,
                    'payload_bytes': payload_bytes,
                    'budget_bytes': int(payload.get('budget_bytes', 0) or 0),
                    'ts': self.now_iso(),
                }
        stats['last_transport_observation'] = {'kind': kind, **payload, 'ts': self.now_iso()}
        self.state_store.replace_mapping('transport_stats', stats)

    def on_dispatcher_observation(self, kind: str, **payload: Any) -> None:
        """Accumulate ingress-dispatcher observations alongside transport diagnostics.

        Args:
            kind: Dispatcher observation kind.
            **payload: Optional observation metadata.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            Dispatcher observations intentionally update the same transport snapshot used by
            the frontend so queue pressure, backpressure rejects and latest-only replacement
            are visible without adding a parallel telemetry channel.
        """
        stats = dict(self.state.transport_stats)
        counters = {
            'accepted': 'dispatcher_accept_count',
            'processed': 'dispatcher_process_count',
            'busy_rejected': 'dispatcher_busy_reject_count',
            'latest_only_replaced': 'dispatcher_latest_only_replace_count',
            'preempted': 'dispatcher_preempt_count',
        }
        key = counters.get(kind)
        if key is not None:
            stats[key] = int(stats.get(key, 0) or 0) + 1
        if payload:
            stats['last_dispatcher_observation'] = {'kind': kind, **payload, 'ts': self.now_iso()}
        self.state_store.replace_mapping('transport_stats', stats)
        self._sync_dispatcher_snapshot()

    def _sync_dispatcher_snapshot(self) -> None:
        """Merge bounded-ingress dispatcher stats into the transport snapshot.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        stats = dict(self.state.transport_stats)
        stats.update(self.dispatcher.stats_snapshot())
        self.state_store.replace_mapping('transport_stats', stats)

    def process_command_queue(self) -> None:
        """Dispatch a bounded batch of queued frontend commands.

        Args:
            None.

        Returns:
            None.

        Raises:
            None. Router failures are handled inside ``CommandDispatcher``.

        Boundary behavior:
            Processing is limited to ``dispatch_batch_max`` commands per timer tick so the
            control callback cannot starve heartbeat, snapshot, or readiness work when the
            operator produces a burst of commands.
        """
        self.dispatcher.process_batch(int(self.get_parameter('dispatch_batch_max').value))
        self.command_router.expire_pending()
        self._expire_runtime_param_transaction()
        self._sync_dispatcher_snapshot()

    def publish_heartbeat(self) -> None:
        self.state_store.set_attr('last_heartbeat_at', self.now_iso())
        self.schedule_send(self.envelopes.event('heartbeat', self.connection_payload()))

    def destroy_node(self) -> bool:
        """Release Web bridge transport resources before delegating to ROS teardown.

        Args:
            None.

        Returns:
            Underlying ``Node.destroy_node`` return value when available, else ``True``.

        Raises:
            None. Cleanup failures are swallowed to preserve shutdown compatibility.
        """
        gateway = getattr(self, 'gateway', None)
        if gateway is not None:
            try:
                gateway.stop()
            except Exception:
                pass
        destroy = getattr(Node, 'destroy_node', None)
        if destroy is None:
            return True
        try:
            return destroy(self)
        except Exception:
            return True



def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = RobotWebBridgeNode()
    if MultiThreadedExecutor is None:
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()
            rclpy.shutdown()
        return
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
