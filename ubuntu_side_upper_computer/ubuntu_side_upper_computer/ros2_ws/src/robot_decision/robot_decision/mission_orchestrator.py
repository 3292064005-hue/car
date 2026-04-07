from __future__ import annotations

"""Mission execution orchestration for patrol and track tasks."""

from dataclasses import dataclass, field
from typing import Any

from geometry_msgs.msg import Twist

from robot_decision.decision_policy import EffectPlan, ModeTransition, SpeakEffect
from robot_decision.patrol_manager import PatrolManager, PatrolStep, PatrolTick
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
        """Construct the patrol manager from configuration or safe defaults.

        Args:
            None.

        Returns:
            Initialized ``PatrolManager`` instance.

        Raises:
            StructuredConfigLoadError: When strict config loading is enabled and loading fails.
            ValueError: When strict config validation is enabled and validation fails.
        """
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
        """Advance patrol/track execution by one timer tick.

        Args:
            None.

        Returns:
            Mission tick plan describing state changes and ROS-visible effects.

        Raises:
            None.

        Boundary behavior:
            The orchestrator mutates only task-related internal state. It does
            not publish ROS messages or apply mode transitions directly.
        """
        with self._node.state_guard():
            if self._node.current_mode == MODE_PATROL:
                return self._evaluate_patrol_tick_locked()
            if self._node.current_mode == MODE_TRACK:
                return self._evaluate_track_tick_locked()
        return MissionTickPlan()

    def _evaluate_patrol_tick_locked(self) -> MissionTickPlan:
        now_sec = self._node.get_clock().now().nanoseconds / 1e9
        tick: PatrolTick = self._node.patrol_manager.update(now_sec)
        plan = MissionTickPlan(patrol_cmd=tick.cmd, notify_state_change=True)
        if tick.step is not None:
            self._node.context.current_step_name = tick.step.name
        self._node.context.patrol_index = self._node.patrol_manager.current_index
        self._node.context.active_action_name = 'start_patrol'
        self._node.context.active_action_phase = 'running' if not tick.finished else self._node.context.active_action_phase
        self._node.context.active_action_progress = self._node.patrol_manager.progress_ratio(now_sec)
        descriptor = self._node.patrol_manager.step_descriptor()
        retry_count = int(descriptor.get('retry_count', 0) or 0)
        retry_limit = int(descriptor.get('retry_limit', 0) or 0)
        self._node.context.active_action_message = tick.transition_reason or self._node.context.current_step_name or 'patrol_running'
        if retry_limit > 0:
            self._node.context.active_action_message = f"{self._node.context.active_action_message}|retry={retry_count}/{retry_limit}"
        if tick.speak_text:
            plan.effect_plan.speaks.append(SpeakEffect(tick.speak_text, SPEAK_PRIORITY_INFO))
        if tick.step is not None and tick.step_completed and tick.step.snapshot_tag and allows_snapshot(self._node.current_mode):
            plan.effect_plan.snapshots.append(tick.step.snapshot_tag)
        if tick.transition_action == 'safe_stop':
            self._node.context.active_action_phase = 'aborted'
            self._node.context.active_action_message = tick.transition_reason or 'patrol_safe_stop'
            plan.transition = ModeTransition(MODE_SAFE_STOP, 'decision', tick.transition_reason or 'patrol_safe_stop')
            return plan
        if tick.transition_action == 'abort':
            self._node.context.active_action_phase = 'aborted'
            self._node.context.active_action_message = tick.transition_reason or 'patrol_aborted'
            plan.transition = ModeTransition(MODE_IDLE, 'decision', tick.transition_reason or 'patrol_aborted')
            return plan
        if self._node.patrol_manager.is_finished():
            self._node.context.patrol_completed = True
            self._node.context.active_action_phase = 'completed'
            self._node.context.active_action_progress = 1.0
            self._node.context.active_action_message = 'patrol_complete'
            plan.transition = ModeTransition(MODE_IDLE, 'decision', 'patrol_complete')
        return plan

    def _evaluate_track_tick_locked(self) -> MissionTickPlan:
        plan = MissionTickPlan(track_cmd=self._node.track_manager.compute_cmd(self._node.last_target), notify_state_change=True)
        self._node.context.active_action_name = 'track_target'
        self._node.context.active_action_phase = 'running'
        self._node.context.active_action_progress = 0.0
        self._node.context.active_action_message = self._node.context.last_target_type or 'tracking'
        return plan
