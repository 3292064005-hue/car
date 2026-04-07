from __future__ import annotations

"""Side-effect adapters for the decision runtime."""

from typing import Any

from geometry_msgs.msg import Twist
from std_msgs.msg import String

from robot_contracts.runtime_param_transport import dumps_runtime_param_apply_result
from robot_decision.decision_policy import EffectPlan, EventEffect, SpeakEffect
from robot_decision.decision_projection import DecisionProjection
from robot_decision.task_policy import allows_snapshot
from robot_utils.message_factory import make_event, make_speak
from robot_msgs.msg import ModeState


class DecisionSideEffects:
    """Own all ROS-visible side effects emitted by the decision layer.

    State mutation happens elsewhere. This adapter is responsible for
    publishing mode, summary, audit, speech, control-command, runtime-parameter,
    and snapshot side effects in one place.
    """

    def __init__(self, *, node: Any) -> None:
        self._node = node
        self._projection = DecisionProjection(node)

    def build_mode_state_message(self) -> ModeState:
        """Build the external mode-state message from current decision state.

        Args:
            None.

        Returns:
            Fresh ``ModeState`` message representing the current decision state.

        Raises:
            None.

        Boundary behavior:
            The method only reads the state under the node lock. It never
            performs implicit transitions or emits audit events.
        """
        msg = ModeState()
        msg.current_mode = self._node.current_mode
        msg.previous_mode = self._node.previous_mode
        msg.requested_by = 'decision'
        msg.reason = self._node.context.last_transition_reason or 'state_publish'
        msg.stamp = self._node.get_clock().now().to_msg()
        return msg

    def publish_mode(self) -> None:
        """Publish the current mode-state snapshot."""
        with self._node.state_guard():
            msg = self.build_mode_state_message()
        self._safe_publish(getattr(self._node, 'mode_pub', None), msg)

    def publish_summary(self) -> None:
        """Publish the external decision summary envelope."""
        self._projection.publish_summary()

    def publish_event(self, category: str, name: str, detail: str, *, level: str = 'info') -> None:
        """Publish one decision-layer event-log record."""
        source_name = 'robot_decision'
        get_name = getattr(self._node, 'get_name', None)
        if callable(get_name):
            try:
                source_name = str(get_name() or source_name)
            except Exception:
                source_name = 'robot_decision'
        self._safe_publish(
            getattr(self._node, 'event_pub', None),
            make_event(self._node, category, name, detail, level=level, source=source_name),
        )

    def publish_mode_transition_event(self, *, requested_by: str, reason: str) -> None:
        """Publish one audit event for the latest mode transition.

        Args:
            requested_by: Transition requester label.
            reason: Human-readable transition reason.

        Returns:
            None.

        Raises:
            None.
        """
        detail = f'{self._node.previous_mode}->{self._node.current_mode} by {requested_by}: {reason}'
        self.publish_event('mode', self._node.current_mode, detail)

    def publish_speak(self, text: str, priority: int, *, source: str = 'decision') -> None:
        """Publish one speech request."""
        self._safe_publish(getattr(self._node, 'speak_pub', None), make_speak(text, priority, source))

    def publish_patrol_cmd(self, cmd: Twist) -> None:
        """Publish one patrol velocity command."""
        self._safe_publish(getattr(self._node, 'patrol_pub', None), cmd)

    def publish_track_cmd(self, cmd: Twist) -> None:
        """Publish one tracking velocity command."""
        self._safe_publish(getattr(self._node, 'track_pub', None), cmd)

    def emit_snapshot(self, reason: str) -> None:
        """Publish one snapshot request when snapshots are currently allowed.

        Args:
            reason: Snapshot reason payload.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            Snapshot requests are ignored while the decision layer is in modes
            that explicitly disallow snapshots.
        """
        with self._node.state_guard():
            if not allows_snapshot(self._node.current_mode):
                return
            req = String()
            req.data = reason
            self._node.context.last_snapshot_reason = reason
        self._safe_publish(getattr(self._node, 'snapshot_pub', None), req)

    def publish_runtime_param_apply_result(self, payload: dict[str, Any]) -> None:
        """Publish one runtime-parameter apply-result payload.

        Args:
            payload: JSON-serializable apply-result payload.

        Returns:
            None.

        Raises:
            None. Telemetry publishing failures are swallowed because they must
            not break decision control flow.
        """
        try:
            msg = String()
            msg.data = dumps_runtime_param_apply_result(payload)
        except Exception:
            return
        self._safe_publish(getattr(self._node, 'runtime_param_apply_pub', None), msg)

    def emit_effect_plan(self, plan: EffectPlan | None) -> None:
        """Publish all effects described by one policy/app-service plan.

        Args:
            plan: Effect plan containing events, speech requests, and snapshots.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            ``None`` and empty plans are ignored. Individual publisher failures
            are isolated so that one bad sink does not block the others.
        """
        if plan is None:
            return
        for event in plan.events:
            self.publish_event(event.category, event.name, event.detail, level=event.level)
        for speak in plan.speaks:
            self.publish_speak(speak.text, speak.priority, source=speak.source)
        for snapshot_reason in plan.snapshots:
            self.emit_snapshot(snapshot_reason)

    def notify_state_change(self) -> None:
        """Notify action waiters that state has changed."""
        runtime = getattr(self._node, 'action_runtime', None)
        if runtime is None:
            return
        try:
            runtime.notify_state_change()
        except Exception:
            return

    def _safe_publish(self, publisher: Any, msg: Any) -> None:
        if publisher is None:
            return
        try:
            publisher.publish(msg)
        except Exception:
            return
