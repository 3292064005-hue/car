from __future__ import annotations

"""System-level runtime orchestration manager for bringup and recovery.

This node turns startup readiness, lifecycle-manager status, runtime
supervision, and decision summary state into one explicit orchestration state
machine. Unlike the report-surface projection used by frontend governance, this
manager is intended to be the single runtime authority for startup, pause,
recovery, degraded, and shutdown phases.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from robot_contracts.runtime_orchestration_registry import runtime_orchestration_runtime_status
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.qos_profiles import qos_for


_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    'startup': ('running', 'degraded', 'recovering', 'shutting_down'),
    'running': ('paused', 'degraded', 'recovering', 'shutting_down'),
    'paused': ('running', 'recovering', 'shutting_down'),
    'degraded': ('running', 'recovering', 'shutting_down'),
    'recovering': ('running', 'paused', 'degraded', 'shutting_down'),
    'shutting_down': (),
}


@dataclass(slots=True)
class RuntimeOrchestrationSnapshot:
    """In-memory snapshot of orchestration inputs and outputs."""

    runtime_supervision: dict[str, Any] = field(default_factory=dict)
    lifecycle_status: dict[str, Any] = field(default_factory=dict)
    decision_summary: dict[str, Any] = field(default_factory=dict)
    web_bridge_ready: bool = False
    shutdown_requested: bool = False
    previous_state: str = 'startup'
    last_transition_reason: str = 'startup_pending'


@dataclass(frozen=True, slots=True)
class RuntimeOrchestrationStatus:
    """One evaluated orchestration status payload."""

    state: str
    phase: str
    reason: str
    ready: bool
    allowed_transitions: tuple[str, ...]
    components: dict[str, dict[str, Any]]
    required_missing: tuple[str, ...]
    runtime_supervision_state: str
    decision_mode: str

    def to_payload(self) -> dict[str, Any]:
        return {
            'state': self.state,
            'phase': self.phase,
            'reason': self.reason,
            'ready': self.ready,
            'allowedTransitions': list(self.allowed_transitions),
            'components': self.components,
            'requiredMissing': list(self.required_missing),
            'runtimeSupervisionState': self.runtime_supervision_state,
            'decisionMode': self.decision_mode,
            'ts': time.time(),
        }


def _payload_dict(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, Mapping) else {}


def _normalized_reasons(payload: Mapping[str, Any]) -> list[str]:
    reasons = payload.get('reasons', [])
    return [str(item) for item in reasons] if isinstance(reasons, list) else []


def evaluate_runtime_orchestration(snapshot: RuntimeOrchestrationSnapshot) -> RuntimeOrchestrationStatus:
    """Evaluate one system-level orchestration state.

    Args:
        snapshot: Current orchestration inputs from runtime supervision,
            lifecycle manager, decision summary, and launch shutdown hooks.

    Returns:
        Stable orchestration status used by runtime nodes, launch barriers, and
        operator-facing summaries.

    Raises:
        None.

    Boundary behavior:
        Missing payloads never raise. They are treated as startup or recovering
        conditions so bringup can remain conservative rather than silently
        reporting readiness.
    """

    runtime_supervision = _payload_dict(snapshot.runtime_supervision)
    lifecycle_status = _payload_dict(snapshot.lifecycle_status)
    decision_summary = _payload_dict(snapshot.decision_summary)

    components = runtime_orchestration_runtime_status(runtime_supervision)
    if 'operator_surface_readiness' in components:
        operator_component = dict(components['operator_surface_readiness'])
        extra_missing = list(operator_component.get('missingFields', []))
        if not bool(snapshot.web_bridge_ready) and 'web_bridge_ready_topic' not in extra_missing:
            extra_missing.append('web_bridge_ready_topic')
        operator_component['status'] = 'ready' if not extra_missing else 'missing_fields'
        operator_component['missingFields'] = extra_missing
        components['operator_surface_readiness'] = operator_component

    required_missing = tuple(
        component_id
        for component_id, item in sorted(components.items())
        if bool(item.get('requiredForMainline')) and bool(item.get('missingFields'))
    )

    runtime_state = str(runtime_supervision.get('state', '') or '').strip().lower() or 'unknown'
    decision_mode = str(decision_summary.get('mode', '') or '').strip().upper()
    safe_stop_recoverable = bool(decision_summary.get('safe_stop_recoverable', False))
    safe_stop_blocked_reason = str(decision_summary.get('safe_stop_blocked_reason', '') or '').strip()
    lifecycle_ready = bool(lifecycle_status.get('ready', False)) if lifecycle_status else False
    reasons = _normalized_reasons(runtime_supervision)

    if snapshot.shutdown_requested:
        state = 'shutting_down'
        reason = 'bringup_shutdown_requested'
    elif not runtime_supervision or runtime_state == 'booting' or bool(required_missing) or not bool(runtime_supervision.get('startupBarrierReady', False)):
        state = 'startup'
        if required_missing:
            reason = f"runtime_orchestration_missing_fields:{','.join(required_missing)}"
        elif not runtime_supervision:
            reason = 'runtime_supervision_unavailable'
        else:
            reason = 'runtime_orchestration_startup_pending'
    elif runtime_state in {'faulted', 'unavailable'} or (lifecycle_status and not lifecycle_ready):
        state = 'recovering'
        reason = str(reasons[0] if reasons else 'runtime_orchestration_recovering')
    elif decision_mode == 'SAFE_STOP':
        if safe_stop_recoverable and not safe_stop_blocked_reason:
            state = 'paused'
            reason = 'safe_stop_recoverable_pause'
        else:
            state = 'recovering'
            reason = safe_stop_blocked_reason or 'safe_stop_requires_recovery'
    elif runtime_state == 'degraded':
        state = 'degraded'
        reason = str(reasons[0] if reasons else 'runtime_orchestration_degraded')
    else:
        state = 'running'
        reason = 'runtime_orchestration_running'

    ready = state in {'running', 'paused'}
    return RuntimeOrchestrationStatus(
        state=state,
        phase=state,
        reason=reason,
        ready=ready,
        allowed_transitions=_ALLOWED_TRANSITIONS.get(state, ()),
        components=components,
        required_missing=required_missing,
        runtime_supervision_state=runtime_state,
        decision_mode=decision_mode,
    )


class RuntimeOrchestrationManagerNode(Node):
    """Publish one authoritative system orchestration state machine."""

    def __init__(self) -> None:
        super().__init__('robot_runtime_orchestration_manager')
        self.declare_parameter('runtime_supervision_topic', '/robot/runtime/supervision')
        self.declare_parameter('lifecycle_status_topic', '/robot/lifecycle_manager/status')
        self.declare_parameter('decision_summary_topic', '/robot/decision/summary')
        self.declare_parameter('web_bridge_ready_topic', '/robot/web_bridge/ready')
        self.declare_parameter('orchestration_topic', '/robot/runtime/orchestration')
        self.declare_parameter('orchestration_ready_topic', '/robot/runtime/orchestration/ready')
        self.declare_parameter('publish_period_sec', 0.5)
        self.callback_groups = build_callback_groups()
        self._snapshot = RuntimeOrchestrationSnapshot()
        self._status_pub = self.create_publisher(String, str(self.get_parameter('orchestration_topic').value), qos_for('status_summary'))
        self._ready_pub = self.create_publisher(Bool, str(self.get_parameter('orchestration_ready_topic').value), qos_for('status_summary'))
        call_with_callback_group(self.create_subscription, String, str(self.get_parameter('runtime_supervision_topic').value), self.on_runtime_supervision, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, str(self.get_parameter('lifecycle_status_topic').value), self.on_lifecycle_status, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, str(self.get_parameter('decision_summary_topic').value), self.on_decision_summary, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, Bool, str(self.get_parameter('web_bridge_ready_topic').value), self.on_web_bridge_ready, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_timer, float(self.get_parameter('publish_period_sec').value), self.publish_status, callback_group=self.callback_groups.background)

    @staticmethod
    def _parse_json_message(msg: String) -> dict[str, Any]:
        try:
            payload = json.loads(str(getattr(msg, 'data', '') or '{}'))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def on_runtime_supervision(self, msg: String) -> None:
        self._snapshot.runtime_supervision = self._parse_json_message(msg)

    def on_lifecycle_status(self, msg: String) -> None:
        self._snapshot.lifecycle_status = self._parse_json_message(msg)

    def on_decision_summary(self, msg: String) -> None:
        self._snapshot.decision_summary = self._parse_json_message(msg)

    def on_web_bridge_ready(self, msg: Bool) -> None:
        self._snapshot.web_bridge_ready = bool(getattr(msg, 'data', False))

    def publish_status(self) -> None:
        status = evaluate_runtime_orchestration(self._snapshot)
        self._snapshot.previous_state = status.state
        self._snapshot.last_transition_reason = status.reason
        payload = status.to_payload()
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        self._status_pub.publish(msg)
        ready_msg = Bool()
        ready_msg.data = bool(status.ready)
        self._ready_pub.publish(ready_msg)

    def destroy_node(self) -> bool:
        self._snapshot.shutdown_requested = True
        try:
            self.publish_status()
        except Exception:
            pass
        return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = RuntimeOrchestrationManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        finally:
            rclpy.shutdown()
