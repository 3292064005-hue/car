from __future__ import annotations

"""Internal command-family handlers for :mod:`robot_web_bridge.command_router`."""

from typing import Any, Mapping

from geometry_msgs.msg import Twist

from robot_msgs.msg import SpeakRequest
from robot_msgs.srv import ResetFault, SaveSnapshot, SetMode


def coerce_float_field(payload: Mapping[str, Any], *, router: Any, meta: Any, default: float, keys: tuple[str, ...]) -> float | None:
    try:
        return router._coerce_float_field(payload, *keys, default=default)
    except ValueError as exc:
        router._reject(meta.event_id, meta.command_type, str(exc), trace_id=meta.trace_id)
        return None


class CommandHandlers:
    """Command-family adapter that keeps router entrypoints stable."""

    def __init__(self, router: Any) -> None:
        self.router = router

    def build_registry(self) -> dict[str, Any]:
        return {
            'set_mode': self.handle_mode_family,
            'start_patrol': self.handle_mode_family,
            'pause_patrol': self.handle_mode_family,
            'stop_patrol': self.handle_mode_family,
            'resume_from_safe_stop': self.handle_mode_family,
            'estop': self.handle_mode_family,
            'teleop_cmd': self.handle_teleop,
            'stop_now': self.handle_stop_now,
            'speak_fixed_text': self.handle_speak_fixed_text,
            'save_snapshot': self.handle_save_snapshot,
            'reset_fault': self.handle_reset_fault,
            'set_param': self.handle_set_param,
            'apply_param_draft': self.handle_apply_param_draft,
            'apply_param_profile': self.handle_apply_param_profile,
        }

    def handle_mode_family(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        requested_mode = str(payload.get('mode', 'IDLE')) if meta.command_type == 'set_mode' else ''
        if meta.command_type == 'start_patrol' or (meta.command_type == 'set_mode' and requested_mode == 'PATROL'):
            self.router._dispatch_patrol_action(self.router._make_action_binding(meta, action_name='start_patrol'), operator_id=operator_id, reason=reason)
            return
        if meta.command_type == 'set_mode' and requested_mode == 'TRACK':
            self.router._dispatch_track_action(self.router._make_action_binding(meta, action_name='track_target'), operator_id=operator_id, reason=reason, payload=payload)
            return
        if meta.command_type in {'pause_patrol', 'stop_patrol'}:
            self.router._request_cancel(self.router._make_action_binding(meta, action_name='start_patrol'), goal_handle=self.router.active_patrol_goal, message='patrol cancel requested', extra={'patrolStatus': 'paused' if meta.command_type == 'pause_patrol' else 'aborted', 'trackEnabled': False})
            self.router._request_cancel(self.router._make_action_binding(meta, action_name='track_target'), goal_handle=self.router.active_track_goal, message='track cancel requested', extra={'trackEnabled': False})
        if not self.router._wait_for_service(self.router.node.mode_client, name='/robot/set_mode'):
            self.router._deny(meta.event_id, meta.command_type, '/robot/set_mode service unavailable', trace_id=meta.trace_id)
            return
        req = SetMode.Request()
        req.requested_by = operator_id
        req.reason = reason
        if hasattr(req, 'trace_id'):
            req.trace_id = meta.trace_id
        if meta.command_type == 'set_mode':
            req.mode = requested_mode or 'IDLE'
        elif meta.command_type == 'start_patrol':
            req.mode = 'PATROL'
        elif meta.command_type in {'pause_patrol', 'stop_patrol', 'resume_from_safe_stop'}:
            req.mode = 'IDLE'
        else:
            req.mode = 'SAFE_STOP'
        future = self.router.node.mode_client.call_async(req)
        self.router.pending_mode_acks[future] = self.router._make_pending_ack(meta, requested_mode=req.mode)
        self.router._register_timeout(future, meta=self.router.pending_mode_acks[future], kind='set_mode_service', action_name='set_mode')
        future.add_done_callback(self.router.on_set_mode_done)
        self.router._audit(meta.event_id, meta.command_type, 'queued', f'mode request queued: {req.mode}')

    def handle_teleop(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
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
        self.router.node.manual_pub.publish(Twist())
        self.router._send_ack(meta.event_id, meta.command_type, 'accepted', 'stop command forwarded', trace_id=meta.trace_id)

    def handle_speak_fixed_text(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        text_id = str(payload.get('text', '') or '').strip()
        if not text_id:
            self.router._reject(meta.event_id, meta.command_type, 'speak_fixed_text requires non-empty text', trace_id=meta.trace_id)
            return
        try:
            priority = self.router._coerce_int_field(payload, 'priority', default=1)
        except ValueError as exc:
            self.router._reject(meta.event_id, meta.command_type, str(exc), trace_id=meta.trace_id)
            return
        req = SpeakRequest()
        req.text_id = text_id
        req.priority = priority
        req.requested_by = operator_id
        if hasattr(req, 'trace_id'):
            req.trace_id = meta.trace_id
        self.router.node.speak_pub.publish(req)
        self.router._send_ack(meta.event_id, meta.command_type, 'accepted', 'speak request forwarded as text_id', trace_id=meta.trace_id)

    def handle_save_snapshot(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        if self.router.snapshot_action_client is not None:
            self.router._dispatch_snapshot_action(self.router._make_action_binding(meta, action_name='save_snapshot'), operator_id=operator_id, reason=reason)
            return
        if not self.router._wait_for_service(self.router.node.snapshot_client, name='/robot/save_snapshot'):
            self.router._deny(meta.event_id, meta.command_type, '/robot/save_snapshot service unavailable', trace_id=meta.trace_id)
            return
        req = SaveSnapshot.Request()
        req.reason = reason
        if hasattr(req, 'trace_id'):
            req.trace_id = meta.trace_id
        future = self.router.node.snapshot_client.call_async(req)
        self.router.pending_snapshot_acks[future] = self.router._make_pending_ack(meta)
        self.router._register_timeout(future, meta=self.router.pending_snapshot_acks[future], kind='save_snapshot_service', action_name='save_snapshot')
        future.add_done_callback(self.router.on_snapshot_done)
        self.router._audit(meta.event_id, meta.command_type, 'queued', 'snapshot request queued')

    def handle_reset_fault(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
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

    def handle_set_param(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        key = str(payload.get('key', '')).strip()
        value = payload.get('value')
        try:
            result_message = self.router.node.apply_runtime_param_update(
                key=key,
                value=value,
                reason=reason,
                trace_id=meta.trace_id,
                command_id=meta.event_id,
                command_type=meta.command_type,
            )
        except Exception as exc:
            self.router._reject(meta.event_id, meta.command_type, str(exc), trace_id=meta.trace_id)
            return
        self.router._send_ack(meta.event_id, meta.command_type, 'accepted', result_message, trace_id=meta.trace_id)

    def handle_apply_param_draft(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        params = payload.get('params')
        if not isinstance(params, Mapping):
            self.router._reject(meta.event_id, meta.command_type, 'apply_param_draft requires params mapping', trace_id=meta.trace_id)
            return
        try:
            result_message = self.router.node.apply_runtime_param_draft(
                params=params,
                reason=reason,
                trace_id=meta.trace_id,
                command_id=meta.event_id,
                command_type=meta.command_type,
            )
        except Exception as exc:
            self.router._reject(meta.event_id, meta.command_type, str(exc), trace_id=meta.trace_id)
            return
        self.router._send_ack(meta.event_id, meta.command_type, 'accepted', result_message, trace_id=meta.trace_id)

    def handle_apply_param_profile(self, *, meta: Any, payload: Mapping[str, Any], reason: str, operator_id: str) -> None:
        profile_name = str(payload.get('profileName', '')).strip()
        try:
            result_message = self.router.node.apply_runtime_param_profile(
                profile_name=profile_name,
                reason=reason,
                trace_id=meta.trace_id,
                command_id=meta.event_id,
                command_type=meta.command_type,
            )
        except Exception as exc:
            self.router._reject(meta.event_id, meta.command_type, str(exc), trace_id=meta.trace_id)
            return
        self.router._send_ack(meta.event_id, meta.command_type, 'accepted', result_message, trace_id=meta.trace_id)
