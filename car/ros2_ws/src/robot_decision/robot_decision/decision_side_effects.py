from __future__ import annotations

"""Side-effect adapters for the decision runtime."""

from typing import Any

from std_msgs.msg import Bool, String

from robot_contracts.runtime_param_transport import dumps_runtime_param_apply_result
from robot_decision.decision_policy import EffectPlan
from robot_decision.decision_projection import DecisionProjection
from robot_decision.task_policy import allows_snapshot
from robot_utils.message_factory import make_event, make_speak
from robot_msgs.msg import ModeState


class DecisionSideEffects:
    """Own all ROS-visible side effects emitted by the decision layer.

    State mutation happens elsewhere. This adapter is responsible for
    publishing mode, summary, audit, speech, navigation intents, control-command,
    runtime-parameter, and snapshot side effects in one place.
    """

    def __init__(self, *, node: Any) -> None:
        self._node = node
        self._projection = DecisionProjection(node)

    def build_mode_state_message(self) -> ModeState:
        msg = ModeState()
        msg.current_mode = self._node.current_mode
        msg.previous_mode = self._node.previous_mode
        msg.requested_by = 'decision'
        msg.reason = self._node.context.last_transition_reason or 'state_publish'
        msg.stamp = self._node.get_clock().now().to_msg()
        return msg

    def publish_mode(self) -> None:
        with self._node.state_guard():
            msg = self.build_mode_state_message()
        self._safe_publish(getattr(self._node, 'mode_pub', None), msg, label='mode_state')

    def publish_summary(self) -> None:
        self._projection.publish_summary()

    def publish_event(self, category: str, name: str, detail: str, *, level: str = 'info') -> None:
        source_name = 'robot_decision'
        get_name = getattr(self._node, 'get_name', None)
        if callable(get_name):
            try:
                source_name = str(get_name() or source_name)
            except Exception as exc:
                self._warn('failed to resolve decision node name for event publication', error=str(exc))
                source_name = 'robot_decision'
        self._safe_publish(
            getattr(self._node, 'event_pub', None),
            make_event(self._node, category, name, detail, level=level, source=source_name),
            label=f'event:{category}/{name}',
        )

    def publish_mode_transition_event(self, *, requested_by: str, reason: str) -> None:
        detail = f'{self._node.previous_mode}->{self._node.current_mode} by {requested_by}: {reason}'
        self.publish_event('mode', self._node.current_mode, detail)

    def publish_speak(self, text: str, priority: int, *, source: str = 'decision') -> None:
        self._safe_publish(getattr(self._node, 'speak_pub', None), make_speak(text, priority, source), label='speak')


    def publish_track_cmd(self, cmd: Twist) -> None:
        self._safe_publish(getattr(self._node, 'track_pub', None), cmd, label='track_cmd')

    def publish_navigation_route(self, route_name: str) -> None:
        """Publish one patrol-route intent into the navigation business chain."""
        if not route_name:
            return
        msg = String()
        msg.data = route_name
        self._safe_publish(getattr(self._node, 'navigation_route_pub', None), msg, label='navigation_route')

    def publish_navigation_goal_id(self, goal_id: str) -> None:
        """Publish one named navigation goal."""
        if not goal_id:
            return
        msg = String()
        msg.data = goal_id
        self._safe_publish(getattr(self._node, 'navigation_goal_id_pub', None), msg, label='navigation_goal_id')

    def publish_navigation_cancel(self, *, reason: str = 'mode_exit') -> None:
        """Cancel the current navigation mission.

        Args:
            reason: Human-readable cancellation reason emitted into the audit log.

        Returns:
            None.

        Raises:
            None.
        """
        msg = Bool()
        msg.data = True
        self._safe_publish(getattr(self._node, 'navigation_cancel_pub', None), msg, label='navigation_cancel')
        self.publish_event('navigation', 'cancel', reason, level='info')

    def emit_snapshot(self, reason: str) -> None:
        with self._node.state_guard():
            if not allows_snapshot(self._node.current_mode):
                return
            req = String()
            req.data = reason
            self._node.context.last_snapshot_reason = reason
        self._safe_publish(getattr(self._node, 'snapshot_pub', None), req, label='snapshot_request')

    def publish_runtime_param_apply_result(self, payload: dict[str, Any]) -> None:
        try:
            msg = String()
            msg.data = dumps_runtime_param_apply_result(payload)
        except Exception as exc:
            self._warn('failed to serialize runtime parameter apply result', error=str(exc))
            return
        self._safe_publish(getattr(self._node, 'runtime_param_apply_pub', None), msg, label='runtime_param_apply_result')

    def emit_effect_plan(self, plan: EffectPlan | None) -> None:
        if plan is None:
            return
        for event in plan.events:
            self.publish_event(event.category, event.name, event.detail, level=event.level)
        for speak in plan.speaks:
            self.publish_speak(speak.text, speak.priority, source=speak.source)
        for snapshot_reason in plan.snapshots:
            self.emit_snapshot(snapshot_reason)

    def notify_state_change(self) -> None:
        runtime = getattr(self._node, 'action_runtime', None)
        if runtime is None:
            return
        try:
            runtime.notify_state_change()
        except Exception as exc:
            self._warn('failed to notify action runtime about decision state change', error=str(exc))

    def _safe_publish(self, publisher: Any, msg: Any, *, label: str) -> None:
        if publisher is None:
            return
        try:
            publisher.publish(msg)
        except Exception as exc:
            self._warn(f'failed to publish {label}', error=str(exc))

    def _warn(self, message: str, **payload: Any) -> None:
        logger_factory = getattr(self._node, 'get_logger', None)
        if not callable(logger_factory):
            return
        try:
            logger = logger_factory()
            suffix = '' if not payload else ' ' + ' '.join(f'{key}={value}' for key, value in sorted(payload.items()))
            logger.warning(f'{message}{suffix}')
        except Exception:
            return
