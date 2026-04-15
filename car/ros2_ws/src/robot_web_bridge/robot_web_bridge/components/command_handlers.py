from __future__ import annotations

"""Internal command-family handlers for :mod:`robot_web_bridge.command_router`."""

from typing import Any, Mapping

from geometry_msgs.msg import Twist

from robot_msgs.msg import SpeakRequest
from robot_msgs.srv import ResetFault, SaveSnapshot, SetMode

from .runtime_param_command_service import RuntimeParamCommandService


def coerce_float_field(payload: Mapping[str, Any], *, router: Any, meta: Any, default: float, keys: tuple[str, ...]) -> float | None:
    """Coerce one numeric payload field and reject the command on failure."""
    try:
        return router._coerce_float_field(payload, *keys, default=default)
    except ValueError as exc:
        router._reject(meta.event_id, meta.command_type, str(exc), trace_id=meta.trace_id)
        return None


class CommandHandlers:
    """Command-family adapter that keeps router entrypoints stable."""

    def __init__(self, router: Any) -> None:
        self.router = router
        self.runtime_param_commands = RuntimeParamCommandService(router)

    def build_registry(self) -> dict[str, Any]:
        return {
            'set_mode': self.handle_set_mode,
            'start_patrol': self.handle_start_patrol,
            'pause_patrol': self.handle_pause_patrol,
            'stop_patrol': self.handle_stop_patrol,
            'resume_from_safe_stop': self.handle_resume_from_safe_stop,
            'estop': self.handle_estop,
            'teleop_cmd': self.handle_teleop,
            'stop_now': self.handle_stop_now,
            'speak_fixed_text': self.handle_speak_fixed_text,
            'save_snapshot': self.handle_save_snapshot,
            'reset_fault': self.handle_reset_fault,
            'apply_param_draft': self.runtime_param_commands.handle_apply_param_draft,
            'apply_param_profile': self.runtime_param_commands.handle_apply_param_profile,
        }

    def _queue_set_mode(self, *, meta: Any, mode: str, reason: str, operator_id: str, action_name: str = 'set_mode') -> None:
        """Queue one authoritative ``/robot/set_mode`` request."""
        requested_mode = str(mode or '').strip().upper()
        if not requested_mode:
            self.router._reject(meta.event_id, meta.command_type, 'requested mode must be non-empty', trace_id=meta.trace_id)
            return
        if not self.router._wait_for_service(self.router.node.mode_client, name='/robot/set_mode'):
            self.router._deny(meta.event_id, meta.command_type, '/robot/set_mode service unavailable', trace_id=meta.trace_id)
            return
        req = SetMode.Request()
        req.requested_by = operator_id
        req.reason = reason
        req.mode = requested_mode
        if hasattr(req, 'trace_id'):
            req.trace_id = meta.trace_id
        future = self.router.node.mode_client.call_async(req)
        self.router.pending_mode_acks[future] = self.router._make_pending_ack(meta, requested_mode=req.mode)
        self.router._register_timeout(future, meta=self.router.pending_mode_acks[future], kind='set_mode_service', action_name=action_name)
        future.add_done_callback(self.router.on_set_mode_done)
        self.router._audit(meta.event_id, meta.command_type, 'queued', f'mode request queued: {req.mode}')

    def handle_set_mode(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        """Handle one generic mode-change request."""
        requested_mode = str(payload.get('mode', '')).strip().upper()
        if not requested_mode:
            self.router._reject(meta.event_id, meta.command_type, 'set_mode requires non-empty mode', trace_id=meta.trace_id)
            return
        if requested_mode == 'PATROL':
            self.router._dispatch_patrol_action(self.router._make_action_binding(meta, action_name='start_patrol'), operator_id=operator_id, reason=reason)
            return
        if requested_mode == 'TRACK':
            self.router._dispatch_track_action(self.router._make_action_binding(meta, action_name='track_target'), operator_id=operator_id, reason=reason, payload=payload)
            return
        self._queue_set_mode(meta=meta, mode=requested_mode, reason=reason, operator_id=operator_id, action_name='set_mode')

    def handle_start_patrol(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        del payload
        self.router._dispatch_patrol_action(self.router._make_action_binding(meta, action_name='start_patrol'), operator_id=operator_id, reason=reason)

    def handle_pause_patrol(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        del payload
        self.router._request_cancel(self.router._make_action_binding(meta, action_name='start_patrol'), goal_handle=self.router.active_patrol_goal, message='patrol cancel requested', extra={'patrolStatus': 'paused', 'trackEnabled': False})
        self.router._request_cancel(self.router._make_action_binding(meta, action_name='track_target'), goal_handle=self.router.active_track_goal, message='track cancel requested', extra={'trackEnabled': False})
        self._queue_set_mode(meta=meta, mode='IDLE', reason=reason, operator_id=operator_id, action_name='pause_patrol')

    def handle_stop_patrol(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        del payload
        self.router._request_cancel(self.router._make_action_binding(meta, action_name='start_patrol'), goal_handle=self.router.active_patrol_goal, message='patrol cancel requested', extra={'patrolStatus': 'aborted', 'trackEnabled': False})
        self.router._request_cancel(self.router._make_action_binding(meta, action_name='track_target'), goal_handle=self.router.active_track_goal, message='track cancel requested', extra={'trackEnabled': False})
        self._queue_set_mode(meta=meta, mode='IDLE', reason=reason, operator_id=operator_id, action_name='stop_patrol')

    def handle_resume_from_safe_stop(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        del payload
        self._queue_set_mode(meta=meta, mode='IDLE', reason=reason, operator_id=operator_id, action_name='resume_from_safe_stop')

    def handle_estop(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        del payload
        self._queue_set_mode(meta=meta, mode='SAFE_STOP', reason=reason, operator_id=operator_id, action_name='estop')

    def handle_teleop(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        del reason, operator_id
        linear = coerce_float_field(payload, router=self.router, meta=meta, default=0.0, keys=('linear', 'vx'))
        if linear is None:
            return
        angular = coerce_float_field(payload, router=self.router, meta=meta, default=0.0, keys=('angular', 'wz'))
        if angular is None:
            return
        twist = Twist()
        twist.linear.x = linear
        twist.angular.z = angular
        self.router.node.manual_pub.publish(twist)
        self.router._send_ack(meta.event_id, meta.command_type, 'accepted', 'teleop command forwarded', trace_id=meta.trace_id)

    def handle_stop_now(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        del payload, reason, operator_id
        self.router.node.manual_pub.publish(Twist())
        self.router._send_ack(meta.event_id, meta.command_type, 'accepted', 'stop command forwarded', trace_id=meta.trace_id)

    def handle_speak_fixed_text(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        if not self.router._wait_for_service(self.router.node.speak_client, name='/robot/voice/speak'):
            self.router._deny(meta.event_id, meta.command_type, '/robot/voice/speak service unavailable', trace_id=meta.trace_id)
            return
        text = str(payload.get('text', '')).strip()
        if not text:
            self.router._reject(meta.event_id, meta.command_type, 'speak_fixed_text requires non-empty text', trace_id=meta.trace_id)
            return
        req = SpeakRequest.Request()
        req.text = text
        req.priority = int(payload.get('priority', 1) or 1)
        req.requested_by = str(payload.get('requestedBy') or operator_id)
        if hasattr(req, 'reason'):
            req.reason = reason
        if hasattr(req, 'trace_id'):
            req.trace_id = meta.trace_id
        future = self.router.node.speak_client.call_async(req)
        self.router.pending_speak_acks[future] = self.router._make_pending_ack(meta)
        self.router._register_timeout(future, meta=self.router.pending_speak_acks[future], kind='speak_service', action_name='speak_fixed_text')
        future.add_done_callback(self.router.on_speak_done)
        self.router._audit(meta.event_id, meta.command_type, 'queued', 'voice request queued')

    def handle_save_snapshot(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        del operator_id
        action_binding = self.router._make_action_binding(meta, action_name='save_snapshot')
        if self.router.snapshot_action_client is not None and self.router._wait_for_action_server(self.router.snapshot_action_client, name='/robot/actions/save_snapshot'):
            self.router._dispatch_snapshot_action(action_binding, reason=reason, payload=payload)
            return
        if not self.router._wait_for_service(self.router.node.snapshot_client, name='/robot/save_snapshot'):
            self.router._deny(meta.event_id, meta.command_type, '/robot/save_snapshot service unavailable', trace_id=meta.trace_id)
            return
        req = SaveSnapshot.Request()
        req.filename = str(payload.get('filename') or '').strip()
        future = self.router.node.snapshot_client.call_async(req)
        self.router.pending_snapshot_acks[future] = self.router._make_pending_ack(meta)
        self.router._register_timeout(future, meta=self.router.pending_snapshot_acks[future], kind='snapshot_service', action_name='save_snapshot')
        future.add_done_callback(self.router.on_snapshot_done)
        self.router._audit(meta.event_id, meta.command_type, 'queued', 'snapshot request queued')

    def handle_reset_fault(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        del payload
        if not self.router._wait_for_service(self.router.node.reset_client, name='/robot/reset_fault'):
            self.router._deny(meta.event_id, meta.command_type, '/robot/reset_fault service unavailable', trace_id=meta.trace_id)
            return
        req = ResetFault.Request()
        req.requested_by = operator_id
        req.reason = reason
        if hasattr(req, 'trace_id'):
            req.trace_id = meta.trace_id
        future = self.router.node.reset_client.call_async(req)
        self.router.pending_reset_acks[future] = self.router._make_pending_ack(meta)
        self.router._register_timeout(future, meta=self.router.pending_reset_acks[future], kind='reset_fault_service', action_name='reset_fault')
        future.add_done_callback(self.router.on_reset_done)
        self.router._audit(meta.event_id, meta.command_type, 'queued', 'fault reset queued')
