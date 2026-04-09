from __future__ import annotations

"""Projection helpers for decision-layer external summaries."""

import json
from typing import Any

from std_msgs.msg import String

from robot_contracts.bridge_contract import command_capability_snapshot


class DecisionProjection:
    """Project internal decision-layer state to external summary topics."""

    def __init__(self, node: Any) -> None:
        self._node = node

    def build_summary_payload(self) -> dict[str, object]:
        """Build the JSON-serializable decision summary payload.

        Args:
            None.

        Returns:
            Dictionary matching the external decision summary contract.

        Raises:
            None.

        Boundary behavior:
            The projection only reads current state. It never mutates node
            fields or emits any side effects.
        """
        guard = getattr(self._node, 'mode_guard', None)
        if guard is None:
            raise RuntimeError('decision projection requires mode_guard')
        safe_stop_recoverable, blocked_reason = guard.safe_stop_recovery_status(require_manual_confirm=False)
        capabilities = command_capability_snapshot(guard.command_context())
        return {
            'mode': self._node.current_mode,
            'previous_mode': self._node.previous_mode,
            'patrol_index': self._node.context.patrol_index,
            'patrol_started': self._node.context.patrol_started,
            'patrol_completed': self._node.context.patrol_completed,
            'track_target_valid': self._node.context.track_target_valid,
            'lost_target_count': self._node.context.lost_target_count,
            'last_qrcode': self._node.context.last_qrcode,
            'last_fault': self._node.context.fault_history[-1] if self._node.context.fault_history else '',
            'last_snapshot_reason': self._node.context.last_snapshot_reason,
            'current_step_name': self._node.context.current_step_name,
            'system_ready_for_patrol': guard.system_ready_for_patrol(),
            'safe_stop_recoverable': safe_stop_recoverable,
            'safe_stop_requires_manual_ack': guard.manual_recovery_required(),
            'safe_stop_blocked_reason': blocked_reason,
            'allowed_target_modes': capabilities['allowedTargetModes'],
            'mode_reasons': capabilities['modeReasons'],
            'command_permissions': capabilities['commandPermissions'],
            'active_action_name': self._node.context.active_action_name,
            'active_action_phase': self._node.context.active_action_phase,
            'active_action_message': self._node.context.active_action_message,
            'active_action_progress': self._node.context.active_action_progress,
            'navigation_state': self._node.context.navigation_state,
            'navigation_route_name': self._node.context.navigation_route_name,
            'navigation_goal_id': self._node.context.navigation_goal_id,
            'navigation_goal_label': self._node.context.navigation_goal_label,
            'navigation_completed_goals': self._node.context.navigation_completed_goals,
            'navigation_total_goals': self._node.context.navigation_total_goals,
            'navigation_progress': self._node.context.navigation_progress,
            'runtime_supervision_state': self._node.context.runtime_supervision_state,
            'runtime_supervision_reasons': list(self._node.context.runtime_supervision_reasons),
        }

    def publish_summary(self) -> None:
        """Publish the external decision summary envelope.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        with self._node.state_guard():
            msg = String()
            msg.data = json.dumps(self.build_summary_payload(), ensure_ascii=False, separators=(',', ':'))
        try:
            self._node.summary_pub.publish(msg)
        except Exception:
            return
