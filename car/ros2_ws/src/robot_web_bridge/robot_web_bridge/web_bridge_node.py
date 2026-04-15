from __future__ import annotations

import ipaddress
import json
import os
from typing import Any, Callable, Mapping

import rclpy
from geometry_msgs.msg import Twist
try:
    from nav_msgs.msg import Path as NavPath
except Exception:  # pragma: no cover - lightweight test stubs may omit nav_msgs
    NavPath = None
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
from robot_contracts.command_policy import SessionPolicy, resolve_session_policy
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
from .internal_command_socket import InternalCommandSocketServer
from .components.runtime_param_coordinator import RuntimeParamCoordinator
from .components.command_surface import CommandSurface
from .components.projection_surface import ProjectionSurface
from .components.observability_surface import ObservabilitySurface
from .components import node_runtime_surface as node_runtime
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
        self.declare_parameter('listen_host', '127.0.0.1')
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
        self.declare_parameter('runtime_param_require_monitor_ack', False)
        self.declare_parameter('operator_ready_topic', '/robot/web_bridge/ready')
        self.declare_parameter('default_session_role', 'observer')
        self.declare_parameter('require_operator_token', True)
        self.declare_parameter('operator_tokens', [])
        self.declare_parameter('internal_command_socket_path', '/tmp/inspection_robot/bridge_internal_command.sock')
        self.declare_parameter('internal_command_auth_token', '')

        self.callback_groups = build_callback_groups()
        self.state = WebBridgeState()
        self.state_store = StateStore(state=self.state, snapshot_sync=self._sync_snapshot_cache)
        self.envelopes = EnvelopeFactory(session_id='robot-web-bridge')

        self.manual_pub = self.create_publisher(Twist, '/robot/manual/cmd_vel', qos_for('control_cmd'))
        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self.speak_pub = self.create_publisher(SpeakRequest, '/robot/speak_req', qos_for('control_cmd'))
        self.runtime_param_pub = self.create_publisher(String, RUNTIME_PARAM_TOPIC, qos_for('status_summary'))
        self.runtime_param_apply_result_sub = self.create_subscription(String, RUNTIME_PARAM_APPLY_RESULT_TOPIC, self.on_runtime_param_apply_result, qos_for('status_summary'))
        self.operator_ready_pub = None
        self.mode_client = self.create_client(SetMode, '/robot/set_mode')
        self.reset_client = self.create_client(ResetFault, '/robot/reset_fault')
        self.snapshot_client = self.create_client(SaveSnapshot, '/robot/save_snapshot')
        self.command_surface = CommandSurface.build(node=self)
        self.command_router = self.command_surface.router
        self.command_lifecycle = self.command_surface.lifecycle
        self.runtime_param_coordinator = self.command_surface.runtime_params
        self.ingress_service = self.command_surface.ingress
        self.readiness_cache = self.command_surface.readiness
        self.dispatcher = self.command_surface.dispatcher
        self.projection_surface = ProjectionSurface.build(node=self)
        self.observability_surface = ObservabilitySurface.build(node=self)
        self.state_projector = self.projection_surface.projector

        call_with_callback_group(self.create_subscription, ModeState, '/robot/mode_state', self.on_mode_state, qos_for('mode_state'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, ChassisState, '/robot/chassis_state', self.on_chassis_state, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, PowerState, '/robot/power_state', self.on_power_state, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, VisionTarget, '/robot/vision/target', self.on_vision_target, qos_for('perception'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/vision/qrcode', self.on_qrcode, qos_for('event_log'), callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_subscription, VoiceCommand, '/robot/voice/cmd', self.on_voice_cmd, qos_for('perception'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/voice/ingress_health', self.observability_surface.projector.on_voice_ingress_health, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, Fault, '/robot/fault', self.on_fault, qos_for('fault_event'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, EventLog, '/robot/events', self.on_event_log, qos_for('event_log'), callback_group=self.callback_groups.io)
        call_with_callback_group(self.create_subscription, SystemStatus, '/robot/system_status', self.on_system_status, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/bridge/summary', self.on_bridge_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/bridge/transport_stats', self.on_transport_stats, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/decision/summary', self.on_decision_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/control/summary', self.observability_surface.projector.on_control_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/monitor/summary', self.observability_surface.projector.on_monitor_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/monitor/diagnostics_json', self.observability_surface.projector.on_monitor_diagnostics_json, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/localization/summary', self.observability_surface.projector.on_localization_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/hardware_interface/summary', self.observability_surface.projector.on_hardware_interface_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/navigation/status', self.observability_surface.projector.on_navigation_status, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/runtime/supervision', self.observability_surface.projector.on_runtime_supervision, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)

        if NavPath is not None:
            call_with_callback_group(self.create_subscription, NavPath, '/robot/navigation/path', self.observability_surface.projector.on_navigation_path, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)

        self.heartbeat_timer = call_with_callback_group(self.create_timer, float(self.get_parameter('heartbeat_period').value), self.publish_heartbeat, callback_group=self.callback_groups.background)
        self.command_timer = call_with_callback_group(self.create_timer, 0.05, self.process_command_queue, callback_group=self.callback_groups.control)
        self.readiness_timer = call_with_callback_group(self.create_timer, float(self.get_parameter('readiness_refresh_period').value), self.refresh_readiness, callback_group=self.callback_groups.background)

        self.snapshot_cache = self.projection_surface.snapshot_cache
        self.gateway = WebGateway(
            host=str(self.get_parameter('listen_host').value),
            port=int(self.get_parameter('listen_port').value),
            ws_path=str(self.get_parameter('ws_path').value),
            snapshot_provider=self.get_cached_snapshot_envelope,
            command_handler=self.ingress_service.handle_ws_message,
            stats_callback=self.on_transport_observation,
            session_policy_resolver=self.resolve_gateway_session_policy,
            outbound_event_transform=self.apply_session_policy_to_event,
            telemetry_payload_budget_bytes=int(self.get_parameter('telemetry_payload_budget_bytes').value),
            control_payload_budget_bytes=int(self.get_parameter('control_payload_budget_bytes').value),
            snapshot_payload_budget_bytes=int(self.get_parameter('snapshot_payload_budget_bytes').value),
        )
        self.internal_command_server = InternalCommandSocketServer(
            socket_path=str(self.get_parameter('internal_command_socket_path').value),
            auth_token=str(self.get_parameter('internal_command_auth_token').value or ''),
            request_handler=self.handle_internal_command,
            stats_callback=self.on_internal_command_socket_event,
        )
        self.state.operator_ready_topic = str(self.get_parameter('operator_ready_topic').value)
        self._refresh_contract_snapshot()
        self.refresh_readiness()
        self._sync_dispatcher_snapshot()
        self._sync_snapshot_cache()
        listener = self.gateway.start()
        internal_listener = self.internal_command_server.start()
        self.refresh_readiness()
        self._mark_operator_ready(reason='websocket_gateway_listening', listener=listener)
        host = str(listener.get('host', self.get_parameter('listen_host').value))
        port = int(listener.get('port', self.get_parameter('listen_port').value))
        path = str(listener.get('ws_path', self.get_parameter('ws_path').value))
        self.get_logger().info(f'robot_web_bridge listening on ws://{host}:{port}{path}')
        self.get_logger().info(f"robot_web_bridge internal command socket listening on {internal_listener.get('socketPath', self.get_parameter('internal_command_socket_path').value)}")

    def now_iso(self) -> str:
        from robot_contracts.bridge_contract import now_iso
        return now_iso()

    def connection_payload(self) -> dict[str, Any]:
        return build_connection_payload(self.state)

    def on_control_summary(self, msg: String) -> None:
        self.observability_surface.projector.on_control_summary(msg)

    def on_monitor_summary(self, msg: String) -> None:
        self.observability_surface.projector.on_monitor_summary(msg)

    def on_monitor_diagnostics_json(self, msg: String) -> None:
        self.observability_surface.projector.on_monitor_diagnostics_json(msg)

    def on_localization_summary(self, msg: String) -> None:
        self.observability_surface.projector.on_localization_summary(msg)

    def on_hardware_interface_summary(self, msg: String) -> None:
        self.observability_surface.projector.on_hardware_interface_summary(msg)

    def on_navigation_status(self, msg: String) -> None:
        self.observability_surface.projector.on_navigation_status(msg)

    def on_voice_ingress_health(self, msg: String) -> None:
        self.observability_surface.projector.on_voice_ingress_health(msg)

    def on_runtime_supervision(self, msg: String) -> None:
        self.observability_surface.projector.on_runtime_supervision(msg)

    def on_navigation_path(self, msg: Any) -> None:
        self.observability_surface.projector.on_navigation_path(msg)

    def resolve_gateway_session_policy(self, metadata: Mapping[str, Any]) -> Mapping[str, Any]:
        """Resolve one websocket client into a permanently read-only bridge session.

        ``robot_web_bridge`` no longer accepts writable command sessions over the
        public websocket transport. External writes must flow through
        ``robot_api_server`` which relays commands over the internal UNIX-domain
        command socket.
        """
        query = metadata.get('query', {}) if isinstance(metadata, Mapping) else {}
        role = str(query.get('role', query.get('sessionRole', '')) or '')
        session_id = str(query.get('sessionId', '') or '')
        default_role = str(self.get_parameter('default_session_role').value or 'observer')
        requested = str(role or default_role).strip().lower() or 'observer'
        requested = requested if requested in {'operator', 'observer', 'readonly'} else 'observer'
        normalized_role = 'observer' if requested == 'readonly' else requested
        effective_session_id = str(session_id or '').strip() or f'{normalized_role}-session'
        policy = SessionPolicy(
            role='observer',
            requested_role=normalized_role,
            session_id=effective_session_id,
            write_enabled=False,
            reason='direct bridge websocket sessions are permanently read-only; use API facade for all writable commands',
            source='bridge_direct_readonly',
            authenticated=False,
        )
        return {
            'role': policy.role,
            'requested_role': policy.requested_role,
            'session_id': policy.session_id,
            'write_enabled': policy.write_enabled,
            'reason': policy.reason,
            'source': policy.source,
            'authenticated': policy.authenticated,
        }

    def apply_session_policy_to_event(self, envelope: dict[str, Any], policy: Mapping[str, Any] | None) -> dict[str, Any]:
        """Overlay one per-session permission policy onto an outbound envelope."""
        if not isinstance(envelope, dict):
            return envelope
        if not isinstance(policy, Mapping):
            return dict(envelope)
        session_policy = SessionPolicy(
            role=str(policy.get('role', 'observer') or 'observer'),
            requested_role=str(policy.get('requested_role', policy.get('role', 'observer')) or 'observer'),
            session_id=str(policy.get('session_id', '') or ''),
            write_enabled=bool(policy.get('write_enabled', False)),
            reason=str(policy.get('reason', '') or 'observer session is read-only'),
            source=str(policy.get('source', 'bridge_ws') or 'bridge_ws'),
            authenticated=bool(policy.get('authenticated', False)),
        )
        cloned = dict(envelope)
        if cloned.get('type') == 'snapshot' and isinstance(cloned.get('payload'), dict):
            payload = dict(cloned['payload'])
            payload['connection'] = self._apply_session_policy_to_connection(dict(payload.get('connection') or {}), session_policy)
            cloned['payload'] = payload
            return cloned
        if cloned.get('type') in {'heartbeat', 'connection_state'} and isinstance(cloned.get('payload'), dict):
            cloned['payload'] = self._apply_session_policy_to_connection(dict(cloned['payload']), session_policy)
            return cloned
        return cloned

    @staticmethod
    def _apply_session_policy_to_connection(connection: dict[str, Any], policy: SessionPolicy) -> dict[str, Any]:
        payload = dict(connection or {})
        payload['sessionRole'] = policy.role
        payload['sessionRequestedRole'] = policy.requested_role
        payload['sessionWriteEnabled'] = bool(policy.write_enabled)
        payload['sessionAccessReason'] = policy.reason
        payload['sessionId'] = policy.session_id
        payload['sessionPolicySource'] = policy.source
        if policy.write_enabled:
            return payload
        permissions = dict(payload.get('commandPermissions') or {})
        for command in list(permissions):
            permissions[command] = {'allowed': False, 'reason': policy.reason}
        payload['allowedTargetModes'] = []
        payload['modeReasons'] = {}
        payload['commandPermissions'] = permissions
        return payload

    def build_command_context(self) -> CommandContext:
        """Project current web-bridge state into the shared command contract context."""
        return node_runtime.build_command_context(self)

    def _refresh_contract_snapshot(self, summary_data: Mapping[str, Any] | None = None) -> None:
        """Refresh the frontend-facing command capability snapshot."""
        node_runtime.refresh_contract_snapshot(self, summary_data)

    def _sync_snapshot_cache(self) -> None:
        self.snapshot_cache.refresh()

    def _ensure_operator_ready_pub(self):
        """Create the operator-ready publisher lazily on the first ready signal.

        Args:
            None.

        Returns:
            Publisher compatible with ``std_msgs/String`` payloads.

        Raises:
            Any publisher-construction failure raised by the ROS node facade.
        """
        publisher = getattr(self, 'operator_ready_pub', None)
        if publisher is not None:
            return publisher
        publisher = self.create_publisher(String, str(self.get_parameter('operator_ready_topic').value), qos_for('status_summary'))
        self.operator_ready_pub = publisher
        return publisher

    def _publish_operator_ready(self, *, create_publisher: bool, listener: Mapping[str, Any] | None = None) -> None:
        """Publish the operator-ready latch once the websocket gateway state changes.

        Args:
            create_publisher: Whether the call is allowed to create the
                operator-ready publisher. Startup readiness uses ``True`` so the
                ready topic only appears after the websocket listener has bound.
                Failure/stopped transitions use ``False`` so startup errors do
                not advertise a ready topic spuriously.
            listener: Optional listener metadata overriding the configured host,
                port, and websocket path when publishing the ready payload.

        Returns:
            None.

        Raises:
            None. Publishing failures are surfaced as policy outcomes but must
            not crash the bridge node during startup or teardown.
        """
        try:
            publisher = getattr(self, 'operator_ready_pub', None)
            if publisher is None:
                if not create_publisher:
                    return
                publisher = self._ensure_operator_ready_pub()
            listener_payload = dict(listener or {})
            msg = String()
            msg.data = json.dumps({
                'ready': bool(self.state.operator_ready),
                'reasons': list(self.state.operator_ready_reasons),
                'topic': self.state.operator_ready_topic,
                'ts': self.now_iso(),
                'host': str(listener_payload.get('host', self.get_parameter('listen_host').value)),
                'port': int(listener_payload.get('port', self.get_parameter('listen_port').value)),
                'wsPath': str(listener_payload.get('ws_path', self.get_parameter('ws_path').value)),
            }, ensure_ascii=False, separators=(',', ':'))
            publisher.publish(msg)
        except Exception as exc:
            publish_policy_outcome(
                self,
                outcome=classify_exception(
                    'web_bridge.operator_ready',
                    exc,
                    code='WEB_BRIDGE_OPERATOR_READY_PUBLISH_FAILED',
                    operator_message='web bridge operator-ready publish failed',
                ),
                event_pub=self.event_pub,
            )

    def _mark_operator_ready(self, *, reason: str, listener: Mapping[str, Any] | None = None) -> None:
        """Mark the websocket operator surface as ready and publish the latch.

        Args:
            reason: Stable readiness reason describing why the surface is ready.
            listener: Optional listener metadata resolved from the websocket hub
                startup handshake.

        Returns:
            None.

        Raises:
            None.
        """
        def _apply(state: Any) -> None:
            state.operator_ready = True
            state.operator_ready_reasons = [str(reason)]
            state.operator_ready_topic = str(self.get_parameter('operator_ready_topic').value)

        self.state_store.mutate(_apply)
        self._publish_operator_ready(create_publisher=True, listener=listener)

    def _mark_operator_unready(self, *, reason: str) -> None:
        """Mark the operator surface unavailable without advertising a fake ready topic.

        Args:
            reason: Stable reason describing why the websocket operator surface
                is unavailable.

        Returns:
            None.

        Raises:
            None.
        """
        def _apply(state: Any) -> None:
            state.operator_ready = False
            state.operator_ready_reasons = [str(reason)]
            state.operator_ready_topic = str(self.get_parameter('operator_ready_topic').value)

        self.state_store.mutate(_apply)
        self._publish_operator_ready(create_publisher=False)

    def _build_snapshot_envelope(self) -> dict[str, Any]:
        return self.envelopes.event('snapshot', self.state.snapshot(mjpeg_url=str(self.get_parameter('mjpeg_url').value), connection=self.connection_payload()))

    def get_cached_snapshot_envelope(self) -> dict[str, Any]:
        return self.snapshot_cache.get()

    def broadcast_snapshot(self) -> None:
        self._sync_snapshot_cache()
        self.schedule_send(self.get_cached_snapshot_envelope())

    @staticmethod
    def _mutate_state_compat(instance: Any, callback: Callable[[Any], None]) -> None:
        """Apply one state mutation for both full runtime nodes and lightweight test doubles."""
        node_runtime.mutate_state_compat(instance, callback)

    @staticmethod
    def _record_trace_id_compat(instance: Any, trace_id: str) -> None:
        """Persist one trace identifier across full runtime nodes and test doubles."""
        node_runtime.record_trace_id_compat(instance, trace_id)

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
        """Record one lifecycle phase when the runtime exposes lifecycle tracking."""
        node_runtime.record_command_phase_compat(instance, event_id, command_type, phase, status, message, trace_id=trace_id, extra=extra)

    def _ingress_service(self) -> IngressService:
        return node_runtime.ingress_service(self)

    def _runtime_param_coordinator(self) -> RuntimeParamCoordinator:
        return node_runtime.runtime_param_coordinator(self)

    def _begin_runtime_param_transaction(self, *, reason: str, trace_id: str = '') -> RuntimeParameterTransaction:
        return node_runtime.begin_runtime_param_transaction(self, reason=reason, trace_id=trace_id)

    def _finalize_runtime_param_transaction(self, *, state_label: str, message: str, ok: bool, trace_id: str = '') -> None:
        node_runtime.finalize_runtime_param_transaction(self, state_label=state_label, message=message, ok=ok, trace_id=trace_id)

    def _consume_runtime_param_apply_result(self, payload: Mapping[str, Any]) -> None:
        node_runtime.consume_runtime_param_apply_result(self, payload)

    def on_runtime_param_apply_result(self, msg: String) -> None:
        """Aggregate consumer runtime-parameter apply acknowledgements."""
        node_runtime.on_runtime_param_apply_result(self, msg)

    def _expire_runtime_param_transaction(self) -> None:
        node_runtime.expire_runtime_param_transaction(self)

    def apply_runtime_param_update(
        self,
        *,
        key: str,
        value: Any,
        reason: str,
        trace_id: str = '',
        command_id: str = '',
        command_type: str = '',
    ) -> str:
        """Apply one bridge-managed runtime parameter mutation.

        Args:
            key: Runtime parameter key.
            value: Target value.
            reason: Operator-visible reason string.
            trace_id: Optional correlation identifier.
            command_id: Optional initiating command identifier.
            command_type: Optional initiating command type.

        Returns:
            Human-readable provisional apply message.

        Raises:
            ValueError: If the runtime-parameter mutation fails validation.
        """
        del reason
        return node_runtime.apply_runtime_param_update(
            self,
            key=key,
            value=value,
            trace_id=trace_id,
            command_id=command_id,
            command_type=command_type,
        )

    def apply_runtime_param_draft(
        self,
        *,
        params: Mapping[str, Any],
        reason: str,
        trace_id: str = '',
        command_id: str = '',
        command_type: str = '',
    ) -> str:
        """Apply one frontend draft batch through the runtime-parameter transaction path.

        Args:
            params: Runtime-parameter mapping provided by the frontend draft.
            reason: Operator-visible reason string.
            trace_id: Optional correlation identifier.
            command_id: Optional initiating command identifier.
            command_type: Optional initiating command type.

        Returns:
            Human-readable provisional apply message.

        Raises:
            ValueError: If the draft payload is invalid or any field fails validation.
        """
        del reason
        return node_runtime.apply_runtime_param_draft(
            self,
            params=params,
            trace_id=trace_id,
            command_id=command_id,
            command_type=command_type,
        )

    def apply_runtime_param_profile(
        self,
        *,
        profile_name: str,
        reason: str,
        trace_id: str = '',
        command_id: str = '',
        command_type: str = '',
    ) -> str:
        """Apply one predefined bridge-managed runtime parameter profile.

        Args:
            profile_name: Target runtime-parameter profile name.
            reason: Operator-visible reason string.
            trace_id: Optional correlation identifier.
            command_id: Optional initiating command identifier.
            command_type: Optional initiating command type.

        Returns:
            Human-readable provisional apply message.

        Raises:
            ValueError: If the runtime-parameter profile is unsupported.
        """
        del reason
        return node_runtime.apply_runtime_param_profile(
            self,
            profile_name=profile_name,
            trace_id=trace_id,
            command_id=command_id,
            command_type=command_type,
        )

    def _match_runtime_profile_name(self, params: Mapping[str, Any]) -> str:
        return node_runtime.match_runtime_profile_name(self, params)

    def _runtime_low_power_threshold(self) -> float:
        """Return the currently effective runtime low-power threshold."""
        return node_runtime.runtime_low_power_threshold(self)

    def _publish_runtime_params(self, *, reason: str, trace_id: str = '') -> None:
        """Publish the effective runtime-parameter state to backend consumers."""
        node_runtime.publish_runtime_params(self, reason=reason, trace_id=trace_id)

    def refresh_stale_flags(self) -> None:
        node_runtime.refresh_stale_flags(self)

    async def handle_internal_command(self, payload: dict[str, Any]) -> None:
        """Dispatch one API-facade command received over the internal command socket."""
        authoritative_policy = {
            'role': 'operator',
            'requested_role': 'operator',
            'session_id': 'robot-api-server',
            'write_enabled': True,
            'reason': 'authoritative API facade internal command socket session',
            'source': 'bridge_internal_command_socket',
            'authenticated': True,
        }
        raw = json.dumps(payload, ensure_ascii=False)
        await self.ingress_service.handle_ws_message(raw, authoritative_policy)

    async def handle_ws_message(self, raw: str) -> None:
        await node_runtime.handle_ws_message(self, raw)

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

    def _projection_surface_or_build(self) -> ProjectionSurface:
        """Return the cached projection surface, building it on first use.

        Args:
            None.

        Returns:
            Cached or newly created ``ProjectionSurface``.

        Raises:
            AttributeError: When the runtime double used in tests lacks
                collaborators required to build a projection surface and no
                prebuilt surface was attached.
        """
        projection_surface = getattr(self, 'projection_surface', None)
        if projection_surface is None:
            projection_surface = ProjectionSurface.build(node=self)
            self.projection_surface = projection_surface
        return projection_surface



    def on_mode_state(self, msg: ModeState) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_mode_state(msg)

    def on_chassis_state(self, msg: ChassisState) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_chassis_state(msg)

    def on_power_state(self, msg: PowerState) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_power_state(msg)

    def on_vision_target(self, msg: VisionTarget) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_vision_target(msg)

    def on_qrcode(self, msg: String) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_qrcode(msg)

    def on_voice_cmd(self, msg: VoiceCommand) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_voice_cmd(msg)

    def on_fault(self, msg: Fault) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_fault(msg)

    def on_event_log(self, msg: EventLog) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_event_log(msg)

    def on_system_status(self, msg: SystemStatus) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_system_status(msg)

    def on_bridge_summary(self, msg: String) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_bridge_summary(msg)

    def on_transport_stats(self, msg: String) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_transport_stats(msg)

    def on_decision_summary(self, msg: String) -> None:
        RobotWebBridgeNode._projection_surface_or_build(self).projector.on_decision_summary(msg)

    def refresh_readiness(self) -> None:
        """Refresh cached service/action readiness outside the command path."""
        node_runtime.refresh_readiness(self)

    def on_internal_command_socket_event(self, kind: str, **payload: Any) -> None:
        """Bridge internal command socket observations into the common transport telemetry lane."""
        self.on_transport_observation(kind, **payload)

    def on_transport_observation(self, kind: str, **payload: Any) -> None:
        """Accumulate websocket transport observations for diagnostics.

        Args:
            kind: Stable transport observation kind emitted by the websocket hub.
            **payload: Observation metadata.

        Returns:
            None.

        Raises:
            None. Listener lifecycle transitions are folded into the operator
            readiness latch but must not crash the bridge node.
        """
        if kind == 'listener_failed':
            self._mark_operator_unready(reason='websocket_gateway_failed')
        elif kind == 'listener_stopped':
            self._mark_operator_unready(reason='websocket_gateway_stopped')
        node_runtime.on_transport_observation(self, kind, **payload)

    def on_dispatcher_observation(self, kind: str, **payload: Any) -> None:
        """Accumulate ingress-dispatcher observations alongside transport diagnostics."""
        node_runtime.on_dispatcher_observation(self, kind, **payload)

    def _sync_dispatcher_snapshot(self) -> None:
        """Merge bounded-ingress dispatcher stats into the transport snapshot."""
        node_runtime.sync_dispatcher_snapshot(self)

    def process_command_queue(self) -> None:
        """Dispatch a bounded batch of queued frontend commands."""
        node_runtime.process_command_queue(self)

    def publish_heartbeat(self) -> None:
        node_runtime.publish_heartbeat(self)

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
        internal_command_server = getattr(self, 'internal_command_server', None)
        if internal_command_server is not None:
            try:
                internal_command_server.stop()
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
