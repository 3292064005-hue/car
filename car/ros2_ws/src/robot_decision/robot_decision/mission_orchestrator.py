from __future__ import annotations

"""Mission execution orchestration for patrol and track tasks."""

from dataclasses import dataclass, field
from typing import Any

from geometry_msgs.msg import Twist

from robot_decision.decision_policy import EffectPlan, ModeTransition, SpeakEffect
from robot_decision.patrol_manager import PatrolManager, PatrolStep
from robot_decision.task_policy import allows_snapshot
from robot_utils.config_loader import load_structured_file
from robot_utils.constants import MODE_IDLE, MODE_PATROL, MODE_SAFE_STOP, MODE_TRACK, SPEAK_PRIORITY_INFO
from robot_utils.error_policy import classify_exception, publish_policy_outcome
from robot_utils.parameter_schema import validate_patrol_config


@dataclass
class MissionTickPlan:
    """Domain plan produced by one patrol/track timer tick."""

    effect_plan: EffectPlan = field(default_factory=EffectPlan)
    transition: ModeTransition | None = None
    patrol_cmd: Twist | None = None
    track_cmd: Twist | None = None
    notify_state_change: bool = False


class MissionOrchestrator:
    """Own patrol/track execution state transitions for the decision layer."""

    def __init__(self, node: Any) -> None:
        self._node = node

    def build_patrol_manager(self) -> PatrolManager:
        config_path = str(self._node.get_parameter('patrol_config_path').value)
        strict_patrol_config = bool(self._node.get_parameter('strict_patrol_config').value)
        allow_default_patrol_fallback = bool(self._node.get_parameter('allow_default_patrol_fallback').value)

        config: object = {}
        if config_path:
            try:
                config = load_structured_file(
                    config_path,
                    {},
                    strict=strict_patrol_config or not allow_default_patrol_fallback,
                    context='patrol config',
                )
                config = validate_patrol_config(config)
            except Exception as exc:
                outcome = classify_exception(
                    'decision.patrol_config',
                    exc,
                    code='PATROL_CONFIG_INVALID',
                    operator_message=f'patrol config invalid: {exc}',
                )
                publish_policy_outcome(self._node, outcome=outcome, event_pub=getattr(self._node, 'event_pub', None))
                if strict_patrol_config or not allow_default_patrol_fallback:
                    raise
                config = {}
        if isinstance(config, dict) and 'patrol' in config:
            config = config['patrol']
        steps_cfg = config.get('steps', []) if isinstance(config, dict) else []
        if steps_cfg:
            return PatrolManager.from_config(steps_cfg)
        step_duration = float(self._node.get_parameter('patrol_step_duration').value)
        return PatrolManager(
            [
                PatrolStep('forward_a', step_duration, 0.15, 0.0, 'patrol_start', 'color', 'forward_a', 0.2, True),
                PatrolStep('scan_left', 1.4, 0.0, 0.55, 'scan_left', 'qrcode', 'scan_left', 0.2, False),
                PatrolStep('forward_b', step_duration, 0.12, 0.0, 'forward_next', 'color', 'forward_b', 0.2, True),
                PatrolStep('scan_right', 1.4, 0.0, -0.55, 'scan_right', 'qrcode', 'scan_right', 0.2, False),
            ]
        )

    def tick_tasks(self) -> MissionTickPlan:
        with self._node.state_guard():
            if self._node.current_mode == MODE_PATROL:
                return self._evaluate_patrol_tick_locked()
            if self._node.current_mode == MODE_TRACK:
                return self._evaluate_track_tick_locked()
        return MissionTickPlan()

    def _evaluate_patrol_tick_locked(self) -> MissionTickPlan:
        """Project navigation-owned patrol status back into the business task model.

        Patrol no longer fabricates a velocity chain directly inside the decision
        layer. Navigation is now the authoritative producer; this method only
        interprets navigation lifecycle state and emits task transitions.
        """
        context = self._node.context
        plan = MissionTickPlan(notify_state_change=True)
        context.active_action_name = 'start_patrol'
        context.active_action_progress = float(context.navigation_progress)
        context.current_step_name = context.navigation_goal_label or context.navigation_goal_id
        context.patrol_index = int(context.navigation_completed_goals)
        context.patrol_started = True
        if context.navigation_state in {'idle', 'route_loaded', 'goal_loaded', 'tracking', 'goal_reached'}:
            context.active_action_phase = 'running'
            context.active_action_message = context.navigation_reason or context.current_step_name or context.navigation_state
            if context.navigation_state == 'goal_reached' and context.current_step_name and allows_snapshot(self._node.current_mode):
                plan.effect_plan.snapshots.append(f'navigation:{context.current_step_name}')
            return plan
        if context.navigation_state == 'route_completed':
            context.patrol_completed = True
            context.active_action_phase = 'completed'
            context.active_action_progress = 1.0
            context.active_action_message = 'patrol_complete'
            plan.transition = ModeTransition(MODE_IDLE, 'decision', 'patrol_complete')
            return plan
        if context.navigation_state == 'cancelled':
            context.active_action_phase = 'cancelled'
            context.active_action_message = context.navigation_reason or 'patrol_cancelled'
            plan.transition = ModeTransition(MODE_IDLE, 'decision', context.navigation_reason or 'patrol_cancelled')
            return plan
        if context.navigation_state == 'failed':
            context.active_action_phase = 'aborted'
            context.active_action_message = context.navigation_reason or 'navigation_failed'
            plan.transition = ModeTransition(MODE_SAFE_STOP, 'decision', context.navigation_reason or 'navigation_failed')
            return plan
        context.active_action_phase = 'running'
        context.active_action_message = context.navigation_reason or context.navigation_state or 'patrol_running'
        return plan

    def _evaluate_track_tick_locked(self) -> MissionTickPlan:
        plan = MissionTickPlan(track_cmd=self._node.track_manager.compute_cmd(self._node.last_target), notify_state_change=True)
        self._node.context.active_action_name = 'track_target'
        self._node.context.active_action_phase = 'running'
        self._node.context.active_action_progress = 0.0
        self._node.context.active_action_message = self._node.context.last_target_type or 'tracking'
        return plan
