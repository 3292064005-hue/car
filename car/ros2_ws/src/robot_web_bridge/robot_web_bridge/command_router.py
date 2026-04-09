from __future__ import annotations

from dataclasses import dataclass
import time
import math
from typing import Any, Mapping

from geometry_msgs.msg import Twist

from robot_contracts.bridge_contract import command_allowed_modes, command_guard, compatibility_ack_status
from robot_contracts.command_policy import SessionPolicy, apply_session_policy_to_context
from robot_utils.action_support import load_robot_actions
from .components.command_handlers import CommandHandlers
from .components import command_runtime_surface as command_runtime

try:
    from rclpy.action import ActionClient
except Exception:  # pragma: no cover - environments without ROS action runtime
    ActionClient = None

SERVICE_WAIT_TIMEOUT_SEC = 0.5
SERVICE_WAIT_RETRIES = 3
DEFAULT_COMMAND_FUTURE_TIMEOUT_SEC = 10.0


def _coerce_float_field(payload: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key not in payload:
            continue
        raw = payload.get(key)
        if raw in (None, ''):
            return float(default)
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'invalid numeric field {key}: {raw!r}') from exc
        if not math.isfinite(value):
            raise ValueError(f'invalid numeric field {key}: {raw!r}')
        return value
    return float(default)


def _coerce_int_field(payload: Mapping[str, Any], key: str, *, default: int) -> int:
    raw = payload.get(key)
    if raw in (None, ''):
        return int(default)
    if isinstance(raw, bool):
        raise ValueError(f'invalid integer field {key}: {raw!r}')
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'invalid integer field {key}: {raw!r}') from exc



@dataclass(frozen=True)
class PendingTimeout:
    """Pending async operation tracked for timeout enforcement."""

    future: Any
    meta: PendingAck
    kind: str
    deadline_monotonic: float
    action_name: str = ''


@dataclass(frozen=True)
class PendingAck:
    """Command acknowledgement metadata retained across async completions.

    Args:
        event_id: Source frontend event identifier.
        command_type: Logical command type.
        requested_mode: Requested target mode for service calls.
        trace_id: Optional correlation identifier propagated from the frontend.

    Raises:
        None.
    """

    event_id: str
    command_type: str
    requested_mode: str = ''
    trace_id: str = ''


@dataclass(frozen=True)
class ActionBinding(PendingAck):
    """Action execution metadata retained across goal/result callbacks.

    Args:
        action_name: Logical action name mirrored into bridge task state.

    Raises:
        None.
    """

    action_name: str = ''


def command_allowed_for_mode(command_type: str, current_mode: str) -> bool:
    allowed = command_allowed_modes(command_type)
    return not allowed or current_mode in allowed


def permission_denial_reason(command_type: str, current_mode: str) -> str:
    allowed = command_allowed_modes(command_type)
    if not allowed:
        return f'unsupported command: {command_type}'
    return f'{command_type} is not allowed while mode={current_mode}; allowed modes: {", ".join(allowed)}'


class CommandRouter:
    _coerce_float_field = staticmethod(_coerce_float_field)
    _coerce_int_field = staticmethod(_coerce_int_field)

    def __init__(self, node: Any, *, operation_timeout_sec: float = DEFAULT_COMMAND_FUTURE_TIMEOUT_SEC, monotonic: Any | None = None) -> None:
        self.node = node
        self._operation_timeout_sec = float(operation_timeout_sec) if float(operation_timeout_sec) > 0.0 else DEFAULT_COMMAND_FUTURE_TIMEOUT_SEC
        self._monotonic = monotonic or time.monotonic
        self._pending_timeouts: dict[int, PendingTimeout] = {}
        self.pending_mode_acks: dict[Any, PendingAck] = {}
        self.pending_reset_acks: dict[Any, PendingAck] = {}
        self.pending_snapshot_acks: dict[Any, PendingAck] = {}
        self._actions = load_robot_actions()
        self.active_patrol_goal = None
        self.active_track_goal = None
        self.active_snapshot_goal = None
        self.patrol_goal_by_command: dict[Any, ActionBinding] = {}
        self.track_goal_by_command: dict[Any, ActionBinding] = {}
        self.snapshot_goal_by_command: dict[Any, ActionBinding] = {}
        self.patrol_result_by_goal: dict[Any, ActionBinding] = {}
        self.track_result_by_goal: dict[Any, ActionBinding] = {}
        self.snapshot_result_by_goal: dict[Any, ActionBinding] = {}
        self.patrol_goal_handle_by_result: dict[Any, Any] = {}
        self.track_goal_handle_by_result: dict[Any, Any] = {}
        self.snapshot_goal_handle_by_result: dict[Any, Any] = {}
        if self._actions and ActionClient is not None:
            self.patrol_action_client = ActionClient(node, self._actions['StartPatrol'], '/robot/actions/start_patrol')
            self.track_action_client = ActionClient(node, self._actions['TrackTarget'], '/robot/actions/track_target')
            self.snapshot_action_client = ActionClient(node, self._actions['SaveSnapshotTask'], '/robot/actions/save_snapshot')
        else:
            self.patrol_action_client = None
            self.track_action_client = None
            self.snapshot_action_client = None
        self._command_handlers = CommandHandlers(self)
        self._handlers = self._command_handlers.build_registry()

    def _audit(self, event_id: str, command_type: str, status: str, message: str) -> None:
        command_runtime.audit(self, event_id, command_type, status, message)

    def _record_phase(self, event_id: str, command_type: str, phase: str, status: str, message: str, *, trace_id: str = '', extra: Mapping[str, Any] | None = None) -> None:
        command_runtime.record_phase(self, event_id, command_type, phase, status, message, trace_id=trace_id, extra=extra)

    def _send_ack(self, event_id: str, command_type: str, lifecycle_status: str, message: str, *, trace_id: str = '', detail: str = '') -> None:
        command_runtime.send_ack(self, event_id, command_type, lifecycle_status, message, trace_id=trace_id, detail=detail)

    def _update_task_state(self, payload: Mapping[str, Any]) -> None:
        command_runtime.update_task_state(self, payload)

    def _deny(self, event_id: str, command_type: str, message: str, *, trace_id: str = '') -> None:
        command_runtime.deny(self, event_id, command_type, message, trace_id=trace_id)

    def _reject(self, event_id: str, command_type: str, message: str, *, trace_id: str = '') -> None:
        command_runtime.reject(self, event_id, command_type, message, trace_id=trace_id)

    def _wait_for_service(self, client: Any, *, name: str) -> bool:
        return command_runtime.wait_for_service(self, client, name=name)

    def _wait_for_action_server(self, client: Any, *, name: str) -> bool:
        return command_runtime.wait_for_action_server(self, client, name=name)


    def _register_timeout(self, future: Any, *, meta: PendingAck, kind: str, action_name: str = '') -> None:
        command_runtime.register_timeout(self, PendingTimeout, future, meta=meta, kind=kind, action_name=action_name)

    def _clear_timeout(self, future: Any) -> PendingTimeout | None:
        return command_runtime.clear_timeout(self, future)

    def _cancel_goal_handle(self, goal_handle: Any, *, action_name: str) -> None:
        command_runtime.cancel_goal_handle(self, goal_handle, action_name=action_name)

    def expire_pending(self, *, now_monotonic: float | None = None) -> int:
        return command_runtime.expire_pending(self, now_monotonic=now_monotonic)

    def _expire_timeout_entry(self, entry: PendingTimeout) -> None:
        meta = entry.meta
        message = f'{entry.kind.replace("_", " ")} timed out'
        if entry.kind == 'set_mode_service':
            self.pending_mode_acks.pop(entry.future, None)
            self._record_phase(meta.event_id, meta.command_type, 'timeout', 'timeout', message, trace_id=meta.trace_id)
            self._send_ack(meta.event_id, meta.command_type, 'timeout', message, trace_id=meta.trace_id)
            return
        if entry.kind == 'reset_fault_service':
            self.pending_reset_acks.pop(entry.future, None)
            self._record_phase(meta.event_id, meta.command_type, 'timeout', 'timeout', message, trace_id=meta.trace_id)
            self._send_ack(meta.event_id, meta.command_type, 'timeout', message, trace_id=meta.trace_id)
            return
        if entry.kind == 'save_snapshot_service':
            self.pending_snapshot_acks.pop(entry.future, None)
            self._record_phase(meta.event_id, meta.command_type, 'timeout', 'timeout', message, trace_id=meta.trace_id)
            self._send_ack(meta.event_id, meta.command_type, 'timeout', message, trace_id=meta.trace_id)
            return
        if entry.kind == 'start_patrol_goal':
            self.patrol_goal_by_command.pop(entry.future, None)
            self._finalize_action(ActionBinding(event_id=meta.event_id, command_type=meta.command_type, requested_mode=meta.requested_mode, trace_id=meta.trace_id, action_name=entry.action_name or 'start_patrol'), lifecycle_status='timeout', message=message, phase='timeout', progress=0.0, extra={'patrolStatus': 'timed_out', 'trackEnabled': False})
            return
        if entry.kind == 'track_target_goal':
            self.track_goal_by_command.pop(entry.future, None)
            self._finalize_action(ActionBinding(event_id=meta.event_id, command_type=meta.command_type, requested_mode=meta.requested_mode, trace_id=meta.trace_id, action_name=entry.action_name or 'track_target'), lifecycle_status='timeout', message=message, phase='timeout', progress=0.0, extra={'trackEnabled': False})
            return
        if entry.kind == 'save_snapshot_goal':
            self.snapshot_goal_by_command.pop(entry.future, None)
            self._finalize_action(ActionBinding(event_id=meta.event_id, command_type=meta.command_type, requested_mode=meta.requested_mode, trace_id=meta.trace_id, action_name=entry.action_name or 'save_snapshot'), lifecycle_status='timeout', message=message, phase='timeout', progress=0.0)
            return
        if entry.kind == 'start_patrol_result':
            self.patrol_result_by_goal.pop(entry.future, None)
            self._cancel_goal_handle(self.patrol_goal_handle_by_result.pop(entry.future, None), action_name='start_patrol')
            self.active_patrol_goal = None
            self._finalize_action(ActionBinding(event_id=meta.event_id, command_type=meta.command_type, requested_mode=meta.requested_mode, trace_id=meta.trace_id, action_name=entry.action_name or 'start_patrol'), lifecycle_status='timeout', message=message, phase='timeout', progress=self.node.state.task.get('actionProgress'), extra={'patrolStatus': 'timed_out', 'trackEnabled': False})
            return
        if entry.kind == 'track_target_result':
            self.track_result_by_goal.pop(entry.future, None)
            self._cancel_goal_handle(self.track_goal_handle_by_result.pop(entry.future, None), action_name='track_target')
            self.active_track_goal = None
            self._finalize_action(ActionBinding(event_id=meta.event_id, command_type=meta.command_type, requested_mode=meta.requested_mode, trace_id=meta.trace_id, action_name=entry.action_name or 'track_target'), lifecycle_status='timeout', message=message, phase='timeout', progress=self.node.state.task.get('actionProgress'), extra={'trackEnabled': False})
            return
        if entry.kind == 'save_snapshot_result':
            self.snapshot_result_by_goal.pop(entry.future, None)
            self._cancel_goal_handle(self.snapshot_goal_handle_by_result.pop(entry.future, None), action_name='save_snapshot')
            self.active_snapshot_goal = None
            self._finalize_action(ActionBinding(event_id=meta.event_id, command_type=meta.command_type, requested_mode=meta.requested_mode, trace_id=meta.trace_id, action_name=entry.action_name or 'save_snapshot'), lifecycle_status='timeout', message=message, phase='timeout', progress=self.node.state.task.get('actionProgress'))

    def _publish_task_feedback(
        self,
        meta: ActionBinding,
        *,
        phase: str,
        message: str,
        progress: float | None = None,
        extra: Mapping[str, Any] | None = None,
        lifecycle_status: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            'lastTaskEvent': self.node.now_iso(),
            'actionName': meta.action_name,
            'actionPhase': phase,
            'actionMessage': message,
            'commandId': meta.event_id,
            'commandType': meta.command_type,
        }
        if progress is not None:
            payload['actionProgress'] = float(progress)
        if extra:
            payload.update(dict(extra))
        self._update_task_state(payload)
        if lifecycle_status is not None:
            phase_status = lifecycle_status
        elif phase in {'queued'}:
            phase_status = 'queued'
        elif phase in {'accepted', 'running', 'cancelling'}:
            phase_status = 'accepted'
        elif phase in {'paused', 'idle'}:
            phase_status = 'applied'
        elif phase == 'completed':
            phase_status = 'completed'
        elif phase == 'cancelled':
            phase_status = 'cancelled'
        elif phase == 'aborted':
            phase_status = 'rejected'
        elif phase == 'timeout':
            phase_status = 'timeout'
        else:
            phase_status = 'applied'
        self._record_phase(meta.event_id, meta.command_type, phase, phase_status, message, trace_id=meta.trace_id, extra=payload)
        self.node.schedule_send(self.node.envelopes.event('task_event', payload, source='ros2', trace_id=meta.trace_id or None))

    def _finalize_action(self, meta: ActionBinding, *, lifecycle_status: str, message: str, phase: str, progress: float | None = None, extra: Mapping[str, Any] | None = None) -> None:
        self._send_ack(meta.event_id, meta.command_type, lifecycle_status, message, trace_id=meta.trace_id)
        self._publish_task_feedback(meta, phase=phase, message=message, progress=progress, extra=extra, lifecycle_status=lifecycle_status)


    def _request_cancel(self, meta: ActionBinding, *, goal_handle: Any, message: str, extra: Mapping[str, Any] | None = None) -> bool:
        if goal_handle is None:
            return False
        try:
            goal_handle.cancel_goal_async()
        except Exception as exc:
            self._reject(meta.event_id, meta.command_type, f'{message}: {exc}', trace_id=meta.trace_id)
            return False
        self._publish_task_feedback(meta, phase='cancelling', message=message, progress=self.node.state.task.get('actionProgress'), extra=extra, lifecycle_status='accepted')
        return True

    def _dispatch_patrol_action(self, meta: ActionBinding, *, operator_id: str, reason: str) -> None:
        if self.patrol_action_client is None:
            self._deny(meta.event_id, meta.command_type, '/robot/actions/start_patrol action unavailable', trace_id=meta.trace_id)
            return
        if not self._wait_for_action_server(self.patrol_action_client, name='/robot/actions/start_patrol'):
            self._deny(meta.event_id, meta.command_type, '/robot/actions/start_patrol action unavailable', trace_id=meta.trace_id)
            return
        goal = self._actions['StartPatrol'].Goal()
        goal.requested_by = operator_id
        goal.reason = reason
        if hasattr(goal, 'trace_id'):
            goal.trace_id = meta.trace_id
        future = self.patrol_action_client.send_goal_async(goal, feedback_callback=self.on_patrol_feedback)
        self.patrol_goal_by_command[future] = meta
        self._register_timeout(future, meta=meta, kind='start_patrol_goal', action_name='start_patrol')
        future.add_done_callback(self.on_patrol_goal_response)
        self._audit(meta.event_id, meta.command_type, 'queued', 'start_patrol action goal queued')
        self._publish_task_feedback(meta, phase='queued', message='start_patrol action goal queued', progress=0.0, extra={'patrolStatus': 'idle'})

    def _dispatch_track_action(self, meta: ActionBinding, *, operator_id: str, reason: str, payload: Mapping[str, Any]) -> None:
        if self.track_action_client is None:
            self._deny(meta.event_id, meta.command_type, '/robot/actions/track_target action unavailable', trace_id=meta.trace_id)
            return
        if not self._wait_for_action_server(self.track_action_client, name='/robot/actions/track_target'):
            self._deny(meta.event_id, meta.command_type, '/robot/actions/track_target action unavailable', trace_id=meta.trace_id)
            return
        goal = self._actions['TrackTarget'].Goal()
        goal.requested_by = operator_id
        goal.reason = reason
        goal.target_type = str(payload.get('targetType', '') or payload.get('target_type', '') or '')
        if hasattr(goal, 'trace_id'):
            goal.trace_id = meta.trace_id
        try:
            goal.min_confidence = _coerce_float_field(payload, 'minConfidence', 'min_confidence', default=0.0)
        except ValueError as exc:
            self._reject(meta.event_id, meta.command_type, str(exc), trace_id=meta.trace_id)
            return
        future = self.track_action_client.send_goal_async(goal, feedback_callback=self.on_track_feedback)
        self.track_goal_by_command[future] = meta
        self._register_timeout(future, meta=meta, kind='track_target_goal', action_name='track_target')
        future.add_done_callback(self.on_track_goal_response)
        self._audit(meta.event_id, meta.command_type, 'queued', 'track_target action goal queued')
        self._publish_task_feedback(meta, phase='queued', message='track_target action goal queued', progress=0.0, extra={'trackEnabled': False})

    def _dispatch_snapshot_action(self, meta: ActionBinding, *, operator_id: str, reason: str) -> None:
        if self.snapshot_action_client is None:
            self._deny(meta.event_id, meta.command_type, '/robot/actions/save_snapshot action unavailable', trace_id=meta.trace_id)
            return
        if not self._wait_for_action_server(self.snapshot_action_client, name='/robot/actions/save_snapshot'):
            self._deny(meta.event_id, meta.command_type, '/robot/actions/save_snapshot action unavailable', trace_id=meta.trace_id)
            return
        goal = self._actions['SaveSnapshotTask'].Goal()
        goal.requested_by = operator_id
        goal.reason = reason
        if hasattr(goal, 'trace_id'):
            goal.trace_id = meta.trace_id
        future = self.snapshot_action_client.send_goal_async(goal, feedback_callback=self.on_snapshot_feedback)
        self.snapshot_goal_by_command[future] = meta
        self._register_timeout(future, meta=meta, kind='save_snapshot_goal', action_name='save_snapshot')
        future.add_done_callback(self.on_snapshot_goal_response)
        self._audit(meta.event_id, meta.command_type, 'queued', 'snapshot action goal queued')
        self._publish_task_feedback(meta, phase='queued', message='save_snapshot action goal queued', progress=0.0)

    def _make_pending_ack(self, meta: ActionBinding, *, requested_mode: str = '') -> PendingAck:
        return PendingAck(event_id=meta.event_id, command_type=meta.command_type, requested_mode=requested_mode, trace_id=meta.trace_id)

    def _make_action_binding(self, meta: ActionBinding, *, action_name: str) -> ActionBinding:
        return ActionBinding(event_id=meta.event_id, command_type=meta.command_type, trace_id=meta.trace_id, action_name=action_name)

    def handle(self, cmd: dict[str, Any]) -> None:
        command_type = str(cmd.get('type', '')).strip()
        event_id = str(cmd.get('event_id', '') or 'frontend-event')
        trace_id = str(cmd.get('trace_id', '') or '')
        payload = cmd.get('payload', {}) if isinstance(cmd.get('payload'), dict) else {}
        reason = str(cmd.get('reason', 'frontend_command'))
        operator_id = str(cmd.get('operator_id', 'frontend-console'))
        if not command_type:
            self._deny(event_id, 'unknown', 'command type is empty', trace_id=trace_id)
            return

        context = self.node.build_command_context()
        raw_session = cmd.get('session_policy', {}) if isinstance(cmd.get('session_policy'), dict) else {}
        if raw_session:
            context = apply_session_policy_to_context(
                context,
                SessionPolicy(
                    role=str(raw_session.get('role', 'observer') or 'observer'),
                    requested_role=str(raw_session.get('requested_role', raw_session.get('role', 'observer')) or 'observer'),
                    session_id=str(raw_session.get('session_id', '') or ''),
                    write_enabled=bool(raw_session.get('write_enabled', False)),
                    reason=str(raw_session.get('reason', '') or 'observer session is read-only'),
                    source=str(raw_session.get('source', 'bridge_ws') or 'bridge_ws'),
                    authenticated=bool(raw_session.get('authenticated', False)),
                ),
            )
        guard = command_guard(command_type, context, payload=payload)
        if not guard.ok:
            self._deny(event_id, command_type, guard.reason, trace_id=trace_id)
            return

        handler = self._handlers.get(command_type)
        if handler is None:
            self._deny(event_id, command_type, f'unsupported command: {command_type}', trace_id=trace_id)
            return
        handler(meta=ActionBinding(event_id=event_id, command_type=command_type, trace_id=trace_id), payload=payload, reason=reason, operator_id=operator_id)

    def on_patrol_goal_response(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.patrol_goal_by_command.pop(future, None)
        if meta is None:
            return
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._reject(meta.event_id, meta.command_type, f'start_patrol action failed: {exc}', trace_id=meta.trace_id)
            return
        if not getattr(goal_handle, 'accepted', False):
            self._reject(meta.event_id, meta.command_type, 'start_patrol action rejected', trace_id=meta.trace_id)
            return
        self.active_patrol_goal = goal_handle
        result_future = goal_handle.get_result_async()
        self.patrol_result_by_goal[result_future] = meta
        self.patrol_goal_handle_by_result[result_future] = goal_handle
        self._register_timeout(result_future, meta=meta, kind='start_patrol_result', action_name='start_patrol')
        result_future.add_done_callback(self.on_patrol_result)
        self._send_ack(meta.event_id, meta.command_type, 'accepted', 'start_patrol action accepted', trace_id=meta.trace_id)
        self._publish_task_feedback(meta, phase='accepted', message='start_patrol action accepted', progress=0.0, extra={'patrolStatus': 'running', 'trackEnabled': False}, lifecycle_status='accepted')

    def on_patrol_feedback(self, feedback_msg: Any) -> None:
        feedback = feedback_msg.feedback
        meta = ActionBinding('runtime', 'start_patrol', action_name='start_patrol')
        payload = {
            'patrolStatus': 'running' if str(getattr(feedback, 'phase', 'running')) in {'accepted', 'running'} else 'paused',
            'currentWaypoint': str(getattr(feedback, 'step_name', '') or '') or None,
            'completedPoints': int(getattr(feedback, 'completed_points', 0) or 0),
            'totalPoints': int(getattr(feedback, 'total_points', 0) or 0),
            'progress': float(getattr(feedback, 'progress', 0.0) or 0.0),
            'trackEnabled': False,
        }
        self._publish_task_feedback(meta, phase=str(getattr(feedback, 'phase', 'running') or 'running'), message=str(getattr(feedback, 'message', '') or ''), progress=float(getattr(feedback, 'progress', 0.0) or 0.0), extra=payload)

    def on_patrol_result(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.patrol_result_by_goal.pop(future, None)
        self.patrol_goal_handle_by_result.pop(future, None)
        self.active_patrol_goal = None
        if meta is None:
            return
        try:
            wrapped = future.result()
            result = wrapped.result
        except Exception as exc:
            self._finalize_action(meta, lifecycle_status='rejected', message=f'start_patrol result failed: {exc}', phase='aborted', progress=0.0)
            return
        message = str(getattr(result, 'message', '') or 'patrol finished')
        success = bool(getattr(result, 'success', False))
        lowered = message.lower()
        if 'cancel' in lowered:
            lifecycle_status = 'cancelled'
            phase = 'cancelled'
            patrol_status = 'aborted'
        elif success:
            lifecycle_status = 'completed'
            phase = 'completed'
            patrol_status = 'completed'
        else:
            lifecycle_status = 'rejected'
            phase = 'aborted'
            patrol_status = 'aborted'
        self._finalize_action(
            meta,
            lifecycle_status=lifecycle_status,
            message=message,
            phase=phase,
            progress=float(getattr(result, 'progress', 0.0) or 0.0),
            extra={
                'patrolStatus': patrol_status,
                'completedPoints': int(getattr(result, 'completed_points', 0) or 0),
                'trackEnabled': False,
            },
        )

    def on_track_goal_response(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.track_goal_by_command.pop(future, None)
        if meta is None:
            return
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._reject(meta.event_id, meta.command_type, f'track_target action failed: {exc}', trace_id=meta.trace_id)
            return
        if not getattr(goal_handle, 'accepted', False):
            self._reject(meta.event_id, meta.command_type, 'track_target action rejected', trace_id=meta.trace_id)
            return
        self.active_track_goal = goal_handle
        result_future = goal_handle.get_result_async()
        self.track_result_by_goal[result_future] = meta
        self.track_goal_handle_by_result[result_future] = goal_handle
        self._register_timeout(result_future, meta=meta, kind='track_target_result', action_name='track_target')
        result_future.add_done_callback(self.on_track_result)
        self._send_ack(meta.event_id, meta.command_type, 'accepted', 'track_target action accepted', trace_id=meta.trace_id)
        self._publish_task_feedback(meta, phase='accepted', message='track_target action accepted', progress=0.0, extra={'trackEnabled': True}, lifecycle_status='accepted')

    def on_track_feedback(self, feedback_msg: Any) -> None:
        feedback = feedback_msg.feedback
        meta = ActionBinding('runtime', 'set_mode', action_name='track_target')
        payload = {
            'trackEnabled': True,
            'currentTargetType': str(getattr(feedback, 'target_type', '') or ''),
            'lostTargetCount': int(getattr(feedback, 'lost_target_count', 0) or 0),
        }
        self._publish_task_feedback(meta, phase='running', message=str(getattr(feedback, 'message', '') or 'tracking'), progress=0.0, extra=payload)

    def on_track_result(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.track_result_by_goal.pop(future, None)
        self.track_goal_handle_by_result.pop(future, None)
        self.active_track_goal = None
        if meta is None:
            return
        try:
            wrapped = future.result()
            result = wrapped.result
        except Exception as exc:
            self._finalize_action(meta, lifecycle_status='rejected', message=f'track_target result failed: {exc}', phase='aborted', progress=0.0, extra={'trackEnabled': False})
            return
        message = str(getattr(result, 'message', '') or 'track finished')
        success = bool(getattr(result, 'success', False))
        lowered = message.lower()
        if 'cancel' in lowered:
            lifecycle_status = 'cancelled'
            phase = 'cancelled'
        elif success:
            lifecycle_status = 'completed'
            phase = 'completed'
        else:
            lifecycle_status = 'rejected'
            phase = 'aborted'
        self._finalize_action(meta, lifecycle_status=lifecycle_status, message=message, phase=phase, progress=0.0, extra={'trackEnabled': False, 'lostTargetCount': int(getattr(result, 'lost_target_count', 0) or 0)})

    def on_snapshot_goal_response(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.snapshot_goal_by_command.pop(future, None)
        if meta is None:
            return
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._reject(meta.event_id, meta.command_type, f'save_snapshot action failed: {exc}', trace_id=meta.trace_id)
            return
        if not getattr(goal_handle, 'accepted', False):
            self._reject(meta.event_id, meta.command_type, 'save_snapshot action rejected', trace_id=meta.trace_id)
            return
        self.active_snapshot_goal = goal_handle
        result_future = goal_handle.get_result_async()
        self.snapshot_result_by_goal[result_future] = meta
        self.snapshot_goal_handle_by_result[result_future] = goal_handle
        self._register_timeout(result_future, meta=meta, kind='save_snapshot_result', action_name='save_snapshot')
        result_future.add_done_callback(self.on_snapshot_action_result)
        self._send_ack(meta.event_id, meta.command_type, 'accepted', 'save_snapshot action accepted', trace_id=meta.trace_id)
        self._publish_task_feedback(meta, phase='accepted', message='save_snapshot action accepted', progress=0.0, lifecycle_status='accepted')

    def on_snapshot_feedback(self, feedback_msg: Any) -> None:
        feedback = feedback_msg.feedback
        meta = ActionBinding('runtime', 'save_snapshot', action_name='save_snapshot')
        self._publish_task_feedback(meta, phase=str(getattr(feedback, 'phase', 'running') or 'running'), message=str(getattr(feedback, 'message', '') or ''), progress=0.0)

    def on_snapshot_action_result(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.snapshot_result_by_goal.pop(future, None)
        self.snapshot_goal_handle_by_result.pop(future, None)
        self.active_snapshot_goal = None
        if meta is None:
            return
        try:
            wrapped = future.result()
            result = wrapped.result
        except Exception as exc:
            self._finalize_action(meta, lifecycle_status='rejected', message=f'save_snapshot result failed: {exc}', phase='aborted', progress=0.0)
            return
        if bool(getattr(result, 'success', False)):
            detail = str(getattr(result, 'filepath', '') or getattr(result, 'message', 'snapshot saved'))
            self._finalize_action(meta, lifecycle_status='completed', message=detail, phase='completed', progress=1.0)
        else:
            message = str(getattr(result, 'message', 'snapshot rejected'))
            self._finalize_action(meta, lifecycle_status='rejected', message=message, phase='aborted', progress=0.0)

    def on_set_mode_done(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.pending_mode_acks.pop(future, None)
        if meta is None:
            return
        try:
            response = future.result()
        except Exception as exc:
            self._send_ack(meta.event_id, meta.command_type, 'rejected', f'set_mode failed: {exc}', trace_id=meta.trace_id)
            return
        action_meta = ActionBinding(
            event_id=meta.event_id,
            command_type=meta.command_type,
            requested_mode=meta.requested_mode,
            trace_id=meta.trace_id,
            action_name='set_mode',
        )
        if bool(getattr(response, 'success', False)):
            message = str(getattr(response, 'message', 'mode changed'))
            lifecycle_status = 'applied'
            phase = 'completed'
            extra: dict[str, Any] = {}
            action_name = 'set_mode'
            if meta.command_type == 'pause_patrol':
                phase = 'paused'
                action_name = 'start_patrol'
                extra = {'patrolStatus': 'paused', 'trackEnabled': False}
            elif meta.command_type == 'stop_patrol':
                phase = 'cancelled'
                lifecycle_status = 'cancelled'
                action_name = 'start_patrol'
                extra = {'patrolStatus': 'aborted', 'trackEnabled': False}
            elif meta.command_type == 'resume_from_safe_stop':
                phase = 'accepted'
                extra = {'trackEnabled': False}
            elif meta.command_type == 'estop':
                phase = 'aborted'
                lifecycle_status = 'completed'
                extra = {'patrolStatus': 'aborted', 'trackEnabled': False}
            elif meta.requested_mode == 'IDLE':
                phase = 'completed'
                extra = {'trackEnabled': False}
            self._send_ack(meta.event_id, meta.command_type, lifecycle_status, message, trace_id=meta.trace_id)
            self._publish_task_feedback(
                ActionBinding(
                    event_id=action_meta.event_id,
                    command_type=action_meta.command_type,
                    requested_mode=action_meta.requested_mode,
                    trace_id=action_meta.trace_id,
                    action_name=action_name,
                ),
                phase=phase,
                message=message,
                progress=self.node.state.task.get('actionProgress'),
                extra=extra,
                lifecycle_status=lifecycle_status,
            )
        else:
            message = str(getattr(response, 'message', 'mode change rejected'))
            self._send_ack(meta.event_id, meta.command_type, 'rejected', message, trace_id=meta.trace_id)
            self._publish_task_feedback(action_meta, phase='aborted', message=message, progress=0.0, lifecycle_status='rejected')

    def on_reset_done(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.pending_reset_acks.pop(future, None)
        if meta is None:
            return
        try:
            response = future.result()
        except Exception as exc:
            self._send_ack(meta.event_id, meta.command_type, 'rejected', f'reset_fault failed: {exc}', trace_id=meta.trace_id)
            return
        action_meta = ActionBinding(event_id=meta.event_id, command_type=meta.command_type, trace_id=meta.trace_id, action_name='reset_fault')
        if bool(getattr(response, 'success', False)):
            message = str(getattr(response, 'message', 'fault reset complete'))
            self._send_ack(meta.event_id, meta.command_type, 'completed', message, trace_id=meta.trace_id)
            self._publish_task_feedback(action_meta, phase='completed', message=message, progress=1.0, lifecycle_status='completed')
        else:
            message = str(getattr(response, 'message', 'fault reset rejected'))
            self._send_ack(meta.event_id, meta.command_type, 'rejected', message, trace_id=meta.trace_id)
            self._publish_task_feedback(action_meta, phase='aborted', message=message, progress=0.0, lifecycle_status='rejected')

    def on_snapshot_done(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.pending_snapshot_acks.pop(future, None)
        if meta is None:
            return
        try:
            response = future.result()
        except Exception as exc:
            self._send_ack(meta.event_id, meta.command_type, 'rejected', f'save_snapshot failed: {exc}', trace_id=meta.trace_id)
            return
        action_meta = ActionBinding(event_id=meta.event_id, command_type=meta.command_type, trace_id=meta.trace_id, action_name='save_snapshot')
        if bool(getattr(response, 'success', False)):
            filepath = str(getattr(response, 'filepath', ''))
            message = str(getattr(response, 'message', 'snapshot saved'))
            detail = f'{message}: {filepath}' if filepath else message
            self._send_ack(meta.event_id, meta.command_type, 'completed', detail, trace_id=meta.trace_id)
            self._publish_task_feedback(action_meta, phase='completed', message=detail, progress=1.0, lifecycle_status='completed')
        else:
            message = str(getattr(response, 'message', 'snapshot rejected'))
            self._send_ack(meta.event_id, meta.command_type, 'rejected', message, trace_id=meta.trace_id)
            self._publish_task_feedback(action_meta, phase='aborted', message=message, progress=0.0, lifecycle_status='rejected')
