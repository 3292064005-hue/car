from __future__ import annotations

"""Mission execution orchestration for patrol and track tasks."""

from dataclasses import dataclass, field
import time
from typing import Any

from robot_decision.decision_policy import EffectPlan, ModeTransition
from robot_decision.task_policy import allows_snapshot
from robot_decision.stage_execution import start_stage
from robot_utils.constants import MODE_IDLE, MODE_PATROL, MODE_SAFE_STOP, MODE_TRACK


@dataclass
class MissionTickPlan:
    """Domain plan produced by one patrol/track timer tick."""

    effect_plan: EffectPlan = field(default_factory=EffectPlan)
    transition: ModeTransition | None = None
    track_cmd: object | None = None
    navigation_route_name: str = ''
    notify_state_change: bool = False


class MissionOrchestrator:
    """Own patrol/track execution state transitions for the decision layer."""

    def __init__(self, node: Any) -> None:
        self._node = node

    def tick_tasks(self) -> MissionTickPlan:
        with self._node.state_guard():
            if self._node.current_mode == MODE_PATROL:
                return self._evaluate_patrol_tick_locked()
            if self._node.current_mode == MODE_TRACK:
                return self._evaluate_track_tick_locked()
        return MissionTickPlan()

    def _stage_graph_locked(self) -> list[dict[str, object]]:
        return self._node.context.task_graph if isinstance(self._node.context.task_graph, list) else []

    def _current_stage_locked(self) -> dict[str, object]:
        task_graph = self._stage_graph_locked()
        if not task_graph:
            return {}
        index = min(max(int(getattr(self._node.context, 'current_task_stage_index', 0) or 0), 0), len(task_graph) - 1)
        self._node.context.current_task_stage_index = index
        return task_graph[index] if 0 <= index < len(task_graph) else {}

    def _publish_current_stage_locked(self, stage: dict[str, object]) -> None:
        self._node.context.current_task_stage_id = str(stage.get('stageId', '') or '')
        self._node.context.current_task_stage_title = str(stage.get('title', '') or '')

    def _set_stage_timeout_locked(self, stage: dict[str, object], *, started: bool) -> None:
        """Record the active stage timeout window in mission context.

        Args:
            stage: Current task-stage payload.
            started: Whether the stage entered an active execution window.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            Timeout accounting only runs for stages that actually started and have
            a positive timeout. Instant-complete or failed stages clear the timer
            window so later patrol ticks cannot trip stale timeout state.
        """
        timeout_sec = max(0.0, float(stage.get('timeoutSec', 0.0) or 0.0))
        self._node.context.current_task_stage_timeout_sec = timeout_sec
        self._node.context.current_task_stage_started_monotonic = time.monotonic() if started and timeout_sec > 0.0 else 0.0

    def _clear_stage_timeout_locked(self) -> None:
        self._node.context.current_task_stage_timeout_sec = 0.0
        self._node.context.current_task_stage_started_monotonic = 0.0

    def start_stage_locked(self, stage: dict[str, object], *, current_stage_completed: bool) -> object:
        """Start one stage and synchronize timeout + navigation context updates.

        Args:
            stage: Task-stage payload from the admitted mission graph.
            current_stage_completed: Whether the previous stage already reached a
                terminal completed state.

        Returns:
            ``StageExecutionResult`` produced by the stage executor.

        Raises:
            None. Stage executors report failure through result status/reason.

        Boundary behavior:
            The mission context is updated consistently for first-stage starts and
            later stage advances so timeout, navigation reason, and failure
            handling cannot drift between call sites.
        """
        self._publish_current_stage_locked(stage)
        result = start_stage(self._node, stage, current_stage_completed=current_stage_completed)
        if result.status == 'started':
            self._set_stage_timeout_locked(stage, started=True)
            self._node.context.navigation_state = 'route_requested'
            self._node.context.navigation_route_name = result.navigation_route_name or str(stage.get('routeName', '') or '')
            self._node.context.navigation_goal_id = ''
            self._node.context.navigation_goal_label = ''
            self._node.context.navigation_completed_goals = 0
            self._node.context.navigation_total_goals = 0
            self._node.context.navigation_progress = 0.0
            self._node.context.navigation_reason = result.reason or f'stage_start:{self._node.context.current_task_stage_id or self._node.context.navigation_route_name}'
            return result
        if result.status == 'completed':
            self._clear_stage_timeout_locked()
            self._node.context.navigation_state = 'task_stage_completed'
            self._node.context.navigation_progress = 1.0
            self._node.context.navigation_reason = result.reason or str(stage.get('successMessage', '') or 'stage_complete')
            return result
        self._clear_stage_timeout_locked()
        self._node.context.navigation_state = 'failed'
        self._node.context.navigation_reason = result.reason or 'task_stage_failed'
        self._node.context.navigation_progress = 0.0
        return result

    def _handle_stage_timeout_locked(self, plan: MissionTickPlan) -> MissionTickPlan | None:
        timeout_sec = float(getattr(self._node.context, 'current_task_stage_timeout_sec', 0.0) or 0.0)
        started_at = float(getattr(self._node.context, 'current_task_stage_started_monotonic', 0.0) or 0.0)
        if timeout_sec <= 0.0 or started_at <= 0.0:
            return None
        if self._node.context.navigation_state in {'route_completed', 'task_stage_completed', 'cancelled', 'failed'}:
            return None
        elapsed_sec = max(0.0, time.monotonic() - started_at)
        if elapsed_sec < timeout_sec:
            return None
        stage_id = self._node.context.current_task_stage_id or 'stage'
        self._clear_stage_timeout_locked()
        self._node.context.navigation_state = 'failed'
        self._node.context.navigation_progress = 0.0
        self._node.context.navigation_reason = f'stage_timeout:{stage_id}'
        self._node.context.active_action_phase = 'aborted'
        self._node.context.active_action_message = self._node.context.navigation_reason
        plan.transition = ModeTransition(MODE_SAFE_STOP, 'decision', self._node.context.navigation_reason)
        return plan

    def _advance_to_next_stage_locked(self, plan: MissionTickPlan) -> bool:
        task_graph = self._stage_graph_locked()
        if not task_graph:
            self._node.context.current_task_stage_index = 0
            self._node.context.current_task_stage_id = ''
            self._node.context.current_task_stage_title = ''
            self._clear_stage_timeout_locked()
            return False
        next_index = int(getattr(self._node.context, 'current_task_stage_index', 0) or 0) + 1
        while next_index < len(task_graph):
            next_stage = task_graph[next_index]
            self._node.context.current_task_stage_index = next_index
            result = self.start_stage_locked(next_stage, current_stage_completed=True)
            if result.status == 'started':
                plan.navigation_route_name = self._node.context.navigation_route_name
                return True
            if result.status == 'completed':
                next_index += 1
                continue
            return False
        self._node.context.current_task_stage_index = len(task_graph) - 1
        self._publish_current_stage_locked(task_graph[-1])
        self._clear_stage_timeout_locked()
        return False

    def _update_task_stage_locked(self) -> None:
        stage = self._current_stage_locked()
        if not stage:
            self._node.context.current_task_stage_id = ''
            self._node.context.current_task_stage_title = ''
            self._clear_stage_timeout_locked()
            return
        self._publish_current_stage_locked(stage)

    def _evaluate_patrol_tick_locked(self) -> MissionTickPlan:
        """Project navigation-owned patrol status back into the business task model.

        Patrol no longer fabricates a velocity chain directly inside the decision
        layer. Navigation is now the authoritative producer; this method only
        interprets navigation lifecycle state and emits task transitions.
        """
        context = self._node.context
        plan = MissionTickPlan(notify_state_change=True)
        self._update_task_stage_locked()
        timeout_plan = self._handle_stage_timeout_locked(plan)
        if timeout_plan is not None:
            return timeout_plan
        context.active_action_name = 'start_patrol'
        context.active_action_progress = float(context.navigation_progress)
        context.current_step_name = context.navigation_goal_label or context.navigation_goal_id or context.current_task_stage_title
        context.patrol_index = int(context.navigation_completed_goals)
        context.patrol_started = True
        if context.navigation_state in {'idle', 'route_loaded', 'goal_loaded', 'tracking', 'aligning', 'goal_reached'}:
            context.active_action_phase = 'running'
            stage_message = context.current_task_stage_title or context.current_step_name
            context.active_action_message = context.navigation_reason or stage_message or context.navigation_state
            if context.navigation_state == 'goal_reached' and context.current_step_name and allows_snapshot(self._node.current_mode):
                plan.effect_plan.snapshots.append(f'navigation:{context.current_step_name}')
            return plan
        if context.navigation_state in {'route_completed', 'task_stage_completed'}:
            advanced = self._advance_to_next_stage_locked(plan)
            if advanced:
                context.active_action_phase = 'running'
                context.active_action_progress = 0.0
                context.active_action_message = context.navigation_reason or context.current_task_stage_title or 'stage_advanced'
                return plan
            if context.navigation_state == 'failed':
                context.active_action_phase = 'aborted'
                context.active_action_message = context.navigation_reason or 'task_stage_failed'
                plan.transition = ModeTransition(MODE_SAFE_STOP, 'decision', context.navigation_reason or 'task_stage_failed')
                return plan
            self._clear_stage_timeout_locked()
            context.patrol_completed = True
            context.active_action_phase = 'completed'
            context.active_action_progress = 1.0
            context.active_action_message = context.navigation_reason or 'patrol_complete'
            plan.transition = ModeTransition(MODE_IDLE, 'decision', context.navigation_reason or 'patrol_complete')
            return plan
        if context.navigation_state in {'blocked', 'degraded'}:
            context.active_action_phase = 'blocked'
            context.active_action_message = context.navigation_reason or context.navigation_state
            context.active_action_progress = float(context.navigation_progress)
            return plan
        if context.navigation_state == 'cancelled':
            self._clear_stage_timeout_locked()
            context.active_action_phase = 'cancelled'
            context.active_action_message = context.navigation_reason or 'patrol_cancelled'
            plan.transition = ModeTransition(MODE_IDLE, 'decision', context.navigation_reason or 'patrol_cancelled')
            return plan
        if context.navigation_state == 'failed':
            self._clear_stage_timeout_locked()
            context.active_action_phase = 'aborted'
            context.active_action_message = context.navigation_reason or 'navigation_failed'
            plan.transition = ModeTransition(MODE_SAFE_STOP, 'decision', context.navigation_reason or 'navigation_failed')
            return plan
        context.active_action_phase = 'blocked'
        context.active_action_message = context.navigation_reason or context.navigation_state or 'navigation_state_unrecognized'
        context.active_action_progress = float(context.navigation_progress)
        return plan

    def _evaluate_track_tick_locked(self) -> MissionTickPlan:
        plan = MissionTickPlan(track_cmd=self._node.track_manager.compute_cmd(self._node.last_target), notify_state_change=True)
        self._node.context.active_action_name = 'track_target'
        self._node.context.active_action_phase = 'running'
        self._node.context.active_action_progress = 0.0
        self._node.context.active_action_message = self._node.context.last_target_type or 'tracking'
        return plan
