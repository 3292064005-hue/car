from __future__ import annotations

"""Asynchronous command execution runtime for :mod:`robot_web_bridge.command_router`.

This service owns pending acknowledgement bookkeeping, timeout enforcement,
action/service result handling, and runtime task-surface publication. The router
remains the transport/application boundary while this component owns execution
state transitions.
"""

from dataclasses import dataclass
from typing import Any, Mapping
import math
import time

from robot_utils.action_support import load_robot_actions

try:
    from rclpy.action import ActionClient
except Exception:  # pragma: no cover - environments without ROS action runtime
    ActionClient = None

from . import command_runtime_surface as command_runtime

SERVICE_WAIT_TIMEOUT_SEC = 0.5
SERVICE_WAIT_RETRIES = 3
DEFAULT_COMMAND_FUTURE_TIMEOUT_SEC = 10.0


@dataclass(frozen=True)
class PendingAck:
    """Command acknowledgement metadata retained across async completions."""

    event_id: str
    command_type: str
    requested_mode: str = ''
    trace_id: str = ''


@dataclass(frozen=True)
class ActionBinding(PendingAck):
    """Action execution metadata retained across goal/result callbacks."""

    action_name: str = ''


@dataclass(frozen=True)
class PendingTimeout:
    """Pending async operation tracked for timeout enforcement."""

    future: Any
    meta: PendingAck
    kind: str
    deadline_monotonic: float
    action_name: str = ''


class CommandExecutionService:
    """Own asynchronous command execution state for one command router.

    Args:
        router: Parent command router exposing runtime-surface helpers and node.
        operation_timeout_sec: Timeout applied to pending service/action futures.
        monotonic: Optional monotonic clock for deterministic tests.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        router: Any,
        *,
        operation_timeout_sec: float = DEFAULT_COMMAND_FUTURE_TIMEOUT_SEC,
        monotonic: Any | None = None,
        action_client_factory: Any | None = None,
        action_loader: Any | None = None,
    ) -> None:
        self._router = router
        self.node = router.node
        value = float(operation_timeout_sec)
        self._operation_timeout_sec = value if value > 0.0 else DEFAULT_COMMAND_FUTURE_TIMEOUT_SEC
        self._monotonic = monotonic or time.monotonic
        self._pending_timeouts: dict[int, PendingTimeout] = {}
        self.pending_mode_acks: dict[Any, PendingAck] = {}
        self.pending_reset_acks: dict[Any, PendingAck] = {}
        self.pending_snapshot_acks: dict[Any, PendingAck] = {}
        self.pending_speak_acks: dict[Any, PendingAck] = {}
        loader = action_loader if action_loader is not None else load_robot_actions
        self._actions = loader()
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
        action_client = action_client_factory if action_client_factory is not None else ActionClient
        if self._actions and action_client is not None:
            self.patrol_action_client = action_client(self.node, self._actions['StartPatrol'], '/robot/actions/start_patrol')
            self.track_action_client = action_client(self.node, self._actions['TrackTarget'], '/robot/actions/track_target')
            self.snapshot_action_client = action_client(self.node, self._actions['SaveSnapshotTask'], '/robot/actions/save_snapshot')
        else:
            self.patrol_action_client = None
            self.track_action_client = None
            self.snapshot_action_client = None

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
        self._router._update_task_state(payload)
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
        self._router._record_phase(meta.event_id, meta.command_type, phase, phase_status, message, trace_id=meta.trace_id, extra=payload)
        self.node.schedule_send(self.node.envelopes.event('task_event', payload, source='ros2', trace_id=meta.trace_id or None))

    def _finalize_action(
        self,
        meta: ActionBinding,
        *,
        lifecycle_status: str,
        message: str,
        phase: str,
        progress: float | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        self._router._send_ack(meta.event_id, meta.command_type, lifecycle_status, message, trace_id=meta.trace_id)
        self._publish_task_feedback(meta, phase=phase, message=message, progress=progress, extra=extra, lifecycle_status=lifecycle_status)

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
            self._router._record_phase(meta.event_id, meta.command_type, 'timeout', 'timeout', message, trace_id=meta.trace_id)
            self._router._send_ack(meta.event_id, meta.command_type, 'timeout', message, trace_id=meta.trace_id)
            return
        if entry.kind == 'reset_fault_service':
            self.pending_reset_acks.pop(entry.future, None)
            self._router._record_phase(meta.event_id, meta.command_type, 'timeout', 'timeout', message, trace_id=meta.trace_id)
            self._router._send_ack(meta.event_id, meta.command_type, 'timeout', message, trace_id=meta.trace_id)
            return
        if entry.kind == 'save_snapshot_service':
            self.pending_snapshot_acks.pop(entry.future, None)
            self._router._record_phase(meta.event_id, meta.command_type, 'timeout', 'timeout', message, trace_id=meta.trace_id)
            self._router._send_ack(meta.event_id, meta.command_type, 'timeout', message, trace_id=meta.trace_id)
            return
        if entry.kind == 'speak_service':
            self.pending_speak_acks.pop(entry.future, None)
            self._router._record_phase(meta.event_id, meta.command_type, 'timeout', 'timeout', message, trace_id=meta.trace_id)
            self._router._send_ack(meta.event_id, meta.command_type, 'timeout', message, trace_id=meta.trace_id)
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

    def _request_cancel(self, meta: ActionBinding, *, goal_handle: Any, message: str, extra: Mapping[str, Any] | None = None) -> bool:
        if goal_handle is None:
            return False
        try:
            goal_handle.cancel_goal_async()
        except Exception as exc:
            self._router._reject(meta.event_id, meta.command_type, f'{message}: {exc}', trace_id=meta.trace_id)
            return False
        self._publish_task_feedback(meta, phase='cancelling', message=message, progress=self.node.state.task.get('actionProgress'), extra=extra, lifecycle_status='accepted')
        return True

    def _dispatch_patrol_action(self, meta: ActionBinding, *, operator_id: str, reason: str) -> None:
        if self.patrol_action_client is None:
            self._router._deny(meta.event_id, meta.command_type, '/robot/actions/start_patrol action unavailable', trace_id=meta.trace_id)
            return
        if not self._router._wait_for_action_server(self.patrol_action_client, name='/robot/actions/start_patrol'):
            self._router._deny(meta.event_id, meta.command_type, '/robot/actions/start_patrol action unavailable', trace_id=meta.trace_id)
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
        self._router._audit(meta.event_id, meta.command_type, 'queued', 'start_patrol action goal queued')
        self._publish_task_feedback(meta, phase='queued', message='start_patrol action goal queued', progress=0.0, extra={'patrolStatus': 'idle'})

    def _dispatch_track_action(self, meta: ActionBinding, *, operator_id: str, reason: str, payload: Mapping[str, Any]) -> None:
        if self.track_action_client is None:
            self._router._deny(meta.event_id, meta.command_type, '/robot/actions/track_target action unavailable', trace_id=meta.trace_id)
            return
        if not self._router._wait_for_action_server(self.track_action_client, name='/robot/actions/track_target'):
            self._router._deny(meta.event_id, meta.command_type, '/robot/actions/track_target action unavailable', trace_id=meta.trace_id)
            return
        goal = self._actions['TrackTarget'].Goal()
        goal.requested_by = operator_id
        goal.reason = reason
        goal.target_type = str(payload.get('targetType', '') or payload.get('target_type', '') or '')
        if hasattr(goal, 'trace_id'):
            goal.trace_id = meta.trace_id
        try:
            goal.min_confidence = self._router._coerce_float_field(payload, 'minConfidence', 'min_confidence', default=0.0)
        except ValueError as exc:
            self._router._reject(meta.event_id, meta.command_type, str(exc), trace_id=meta.trace_id)
            return
        future = self.track_action_client.send_goal_async(goal, feedback_callback=self.on_track_feedback)
        self.track_goal_by_command[future] = meta
        self._register_timeout(future, meta=meta, kind='track_target_goal', action_name='track_target')
        future.add_done_callback(self.on_track_goal_response)
        self._router._audit(meta.event_id, meta.command_type, 'queued', 'track_target action goal queued')
        self._publish_task_feedback(meta, phase='queued', message='track_target action goal queued', progress=0.0, extra={'trackEnabled': False})

    def _dispatch_snapshot_action(self, meta: ActionBinding, *, operator_id: str = '', reason: str = '', payload: Mapping[str, Any] | None = None) -> None:
        del payload
        if self.snapshot_action_client is None:
            self._router._deny(meta.event_id, meta.command_type, '/robot/actions/save_snapshot action unavailable', trace_id=meta.trace_id)
            return
        if not self._router._wait_for_action_server(self.snapshot_action_client, name='/robot/actions/save_snapshot'):
            self._router._deny(meta.event_id, meta.command_type, '/robot/actions/save_snapshot action unavailable', trace_id=meta.trace_id)
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
        self._router._audit(meta.event_id, meta.command_type, 'queued', 'save_snapshot action goal queued')
        self._publish_task_feedback(meta, phase='queued', message='save_snapshot action goal queued', progress=0.0)

    def _make_pending_ack(self, meta: ActionBinding, *, requested_mode: str = '') -> PendingAck:
        return PendingAck(event_id=meta.event_id, command_type=meta.command_type, requested_mode=requested_mode, trace_id=meta.trace_id)

    def _make_action_binding(self, meta: ActionBinding, *, action_name: str) -> ActionBinding:
        return ActionBinding(event_id=meta.event_id, command_type=meta.command_type, trace_id=meta.trace_id, action_name=action_name)

    def _make_action_binding_from_request(self, request: Any) -> ActionBinding:
        return ActionBinding(event_id=request.event_id, command_type=request.command_type, trace_id=request.trace_id)

    def on_patrol_goal_response(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.patrol_goal_by_command.pop(future, None)
        if meta is None:
            return
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._router._reject(meta.event_id, meta.command_type, f'start_patrol action failed: {exc}', trace_id=meta.trace_id)
            return
        if not getattr(goal_handle, 'accepted', False):
            self._router._reject(meta.event_id, meta.command_type, 'start_patrol action rejected', trace_id=meta.trace_id)
            return
        self.active_patrol_goal = goal_handle
        result_future = goal_handle.get_result_async()
        self.patrol_result_by_goal[result_future] = meta
        self.patrol_goal_handle_by_result[result_future] = goal_handle
        self._register_timeout(result_future, meta=meta, kind='start_patrol_result', action_name='start_patrol')
        result_future.add_done_callback(self.on_patrol_result)
        self._router._send_ack(meta.event_id, meta.command_type, 'accepted', 'start_patrol action accepted', trace_id=meta.trace_id)
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
        self._finalize_action(meta, lifecycle_status=lifecycle_status, message=message, phase=phase, progress=float(getattr(result, 'progress', 0.0) or 0.0), extra={'patrolStatus': patrol_status, 'completedPoints': int(getattr(result, 'completed_points', 0) or 0), 'trackEnabled': False})

    def on_track_goal_response(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.track_goal_by_command.pop(future, None)
        if meta is None:
            return
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._router._reject(meta.event_id, meta.command_type, f'track_target action failed: {exc}', trace_id=meta.trace_id)
            return
        if not getattr(goal_handle, 'accepted', False):
            self._router._reject(meta.event_id, meta.command_type, 'track_target action rejected', trace_id=meta.trace_id)
            return
        self.active_track_goal = goal_handle
        result_future = goal_handle.get_result_async()
        self.track_result_by_goal[result_future] = meta
        self.track_goal_handle_by_result[result_future] = goal_handle
        self._register_timeout(result_future, meta=meta, kind='track_target_result', action_name='track_target')
        result_future.add_done_callback(self.on_track_result)
        self._router._send_ack(meta.event_id, meta.command_type, 'accepted', 'track_target action accepted', trace_id=meta.trace_id)
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
            self._router._reject(meta.event_id, meta.command_type, f'save_snapshot action failed: {exc}', trace_id=meta.trace_id)
            return
        if not getattr(goal_handle, 'accepted', False):
            self._router._reject(meta.event_id, meta.command_type, 'save_snapshot action rejected', trace_id=meta.trace_id)
            return
        self.active_snapshot_goal = goal_handle
        result_future = goal_handle.get_result_async()
        self.snapshot_result_by_goal[result_future] = meta
        self.snapshot_goal_handle_by_result[result_future] = goal_handle
        self._register_timeout(result_future, meta=meta, kind='save_snapshot_result', action_name='save_snapshot')
        result_future.add_done_callback(self.on_snapshot_action_result)
        self._router._send_ack(meta.event_id, meta.command_type, 'accepted', 'save_snapshot action accepted', trace_id=meta.trace_id)
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

    def _mode_command_outcome(self, meta: PendingAck) -> tuple[str, str, str, dict[str, Any]]:
        """Resolve one completed mode-service command into lifecycle/task semantics."""
        action_name = 'set_mode'
        lifecycle_status = 'applied'
        phase = 'completed'
        extra: dict[str, Any] = {}
        if meta.command_type == 'pause_patrol':
            action_name = 'pause_patrol'
            phase = 'paused'
            extra = {'patrolStatus': 'paused', 'trackEnabled': False}
        elif meta.command_type == 'stop_patrol':
            action_name = 'stop_patrol'
            lifecycle_status = 'cancelled'
            phase = 'cancelled'
            extra = {'patrolStatus': 'aborted', 'trackEnabled': False}
        elif meta.command_type == 'resume_from_safe_stop':
            action_name = 'resume_from_safe_stop'
            phase = 'completed'
            extra = {'trackEnabled': False}
        elif meta.command_type == 'estop':
            action_name = 'estop'
            lifecycle_status = 'completed'
            phase = 'aborted'
            extra = {'patrolStatus': 'aborted', 'trackEnabled': False}
        elif meta.requested_mode == 'IDLE':
            extra = {'trackEnabled': False}
        return lifecycle_status, phase, action_name, extra

    def on_set_mode_done(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.pending_mode_acks.pop(future, None)
        if meta is None:
            return
        try:
            response = future.result()
        except Exception as exc:
            self._router._send_ack(meta.event_id, meta.command_type, 'rejected', f'set_mode failed: {exc}', trace_id=meta.trace_id)
            return
        action_meta = ActionBinding(event_id=meta.event_id, command_type=meta.command_type, requested_mode=meta.requested_mode, trace_id=meta.trace_id, action_name='set_mode')
        if bool(getattr(response, 'success', False)):
            message = str(getattr(response, 'message', 'mode changed'))
            lifecycle_status, phase, action_name, extra = self._mode_command_outcome(meta)
            self._router._send_ack(meta.event_id, meta.command_type, lifecycle_status, message, trace_id=meta.trace_id)
            self._publish_task_feedback(ActionBinding(event_id=action_meta.event_id, command_type=action_meta.command_type, requested_mode=action_meta.requested_mode, trace_id=action_meta.trace_id, action_name=action_name), phase=phase, message=message, progress=self.node.state.task.get('actionProgress'), extra=extra, lifecycle_status=lifecycle_status)
        else:
            message = str(getattr(response, 'message', 'mode change rejected'))
            self._router._send_ack(meta.event_id, meta.command_type, 'rejected', message, trace_id=meta.trace_id)
            self._publish_task_feedback(action_meta, phase='aborted', message=message, progress=0.0, lifecycle_status='rejected')

    def on_reset_done(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.pending_reset_acks.pop(future, None)
        if meta is None:
            return
        try:
            response = future.result()
        except Exception as exc:
            self._router._send_ack(meta.event_id, meta.command_type, 'rejected', f'reset_fault failed: {exc}', trace_id=meta.trace_id)
            return
        action_meta = ActionBinding(event_id=meta.event_id, command_type=meta.command_type, trace_id=meta.trace_id, action_name='reset_fault')
        if bool(getattr(response, 'success', False)):
            message = str(getattr(response, 'message', 'fault reset complete'))
            self._router._send_ack(meta.event_id, meta.command_type, 'completed', message, trace_id=meta.trace_id)
            self._publish_task_feedback(action_meta, phase='completed', message=message, progress=1.0, lifecycle_status='completed')
        else:
            message = str(getattr(response, 'message', 'fault reset rejected'))
            self._router._send_ack(meta.event_id, meta.command_type, 'rejected', message, trace_id=meta.trace_id)
            self._publish_task_feedback(action_meta, phase='aborted', message=message, progress=0.0, lifecycle_status='rejected')

    def on_snapshot_done(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.pending_snapshot_acks.pop(future, None)
        if meta is None:
            return
        try:
            response = future.result()
        except Exception as exc:
            self._router._send_ack(meta.event_id, meta.command_type, 'rejected', f'save_snapshot failed: {exc}', trace_id=meta.trace_id)
            return
        action_meta = ActionBinding(event_id=meta.event_id, command_type=meta.command_type, trace_id=meta.trace_id, action_name='save_snapshot')
        if bool(getattr(response, 'success', False)):
            filepath = str(getattr(response, 'filepath', ''))
            message = str(getattr(response, 'message', 'snapshot saved'))
            detail = f'{message}: {filepath}' if filepath else message
            self._router._send_ack(meta.event_id, meta.command_type, 'completed', detail, trace_id=meta.trace_id)
            self._publish_task_feedback(action_meta, phase='completed', message=detail, progress=1.0, lifecycle_status='completed')
        else:
            message = str(getattr(response, 'message', 'snapshot rejected'))
            self._router._send_ack(meta.event_id, meta.command_type, 'rejected', message, trace_id=meta.trace_id)
            self._publish_task_feedback(action_meta, phase='aborted', message=message, progress=0.0, lifecycle_status='rejected')

    def on_speak_done(self, future: Any) -> None:
        self._clear_timeout(future)
        meta = self.pending_speak_acks.pop(future, None)
        if meta is None:
            return
        try:
            response = future.result()
        except Exception as exc:
            self._router._send_ack(meta.event_id, meta.command_type, 'rejected', f'speak_fixed_text failed: {exc}', trace_id=meta.trace_id)
            return
        if bool(getattr(response, 'success', True)):
            message = str(getattr(response, 'message', 'voice request accepted'))
            self._router._send_ack(meta.event_id, meta.command_type, 'completed', message, trace_id=meta.trace_id)
        else:
            message = str(getattr(response, 'message', 'voice request rejected'))
            self._router._send_ack(meta.event_id, meta.command_type, 'rejected', message, trace_id=meta.trace_id)
