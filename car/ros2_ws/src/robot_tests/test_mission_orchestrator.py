from __future__ import annotations

import time
from types import SimpleNamespace

from geometry_msgs.msg import Twist
from robot_decision.decision_policy import ModeTransition
from robot_decision.mission_context import MissionContext
from robot_decision.mission_orchestrator import MissionOrchestrator
from robot_utils.constants import MODE_PATROL


class _Clock:
    class _Now:
        def __init__(self) -> None:
            self.nanoseconds = 0
    def now(self):
        return self._Now()


class _Node:
    def __init__(self) -> None:
        self.current_mode = MODE_PATROL
        self.context = MissionContext()
        self.track_manager = SimpleNamespace(compute_cmd=lambda target: Twist())
        self.last_target = None
    def state_guard(self):
        class _Guard:
            def __enter__(self): return None
            def __exit__(self, exc_type, exc, tb): return False
        return _Guard()
    def get_clock(self):
        return _Clock()


def test_mission_orchestrator_patrol_follows_navigation_status_without_direct_velocity_side_effects() -> None:
    node = _Node()
    node.context.navigation_state = 'goal_reached'
    node.context.navigation_goal_label = 'A-01'
    node.context.navigation_completed_goals = 1
    node.context.navigation_total_goals = 4
    node.context.navigation_progress = 0.25
    node.context.navigation_reason = 'goal_reached'

    plan = MissionOrchestrator(node).tick_tasks()

    assert plan.effect_plan.snapshots == ['navigation:A-01']
    assert plan.transition is None
    assert node.context.active_action_phase == 'running'
    assert node.context.active_action_progress == 0.25


def test_mission_orchestrator_patrol_completes_when_navigation_route_finishes() -> None:
    node = _Node()
    node.context.navigation_state = 'route_completed'
    node.context.navigation_total_goals = 3
    node.context.navigation_completed_goals = 3
    node.context.navigation_progress = 1.0
    node.context.runtime_supervision_state = 'ready'

    plan = MissionOrchestrator(node).tick_tasks()

    assert isinstance(plan.transition, ModeTransition)
    assert plan.transition.new_mode == 'IDLE'
    assert node.context.active_action_phase == 'completed'
    assert node.context.patrol_completed is True


def test_mission_orchestrator_patrol_safe_stops_when_navigation_fails() -> None:
    node = _Node()
    node.context.navigation_state = 'failed'
    node.context.navigation_reason = 'planner_timeout'

    plan = MissionOrchestrator(node).tick_tasks()

    assert isinstance(plan.transition, ModeTransition)
    assert plan.transition.new_mode == 'SAFE_STOP'
    assert plan.transition.reason == 'planner_timeout'
    assert node.context.active_action_phase == 'aborted'


def test_mission_orchestrator_patrol_keeps_running_while_aligning_terminal_yaw() -> None:
    node = _Node()
    node.context.navigation_state = 'aligning'
    node.context.navigation_goal_label = 'dock'
    node.context.navigation_completed_goals = 0
    node.context.navigation_total_goals = 1
    node.context.navigation_progress = 0.0
    node.context.navigation_reason = 'align_yaw:dock'

    plan = MissionOrchestrator(node).tick_tasks()

    assert plan.transition is None
    assert node.context.active_action_phase == 'running'
    assert node.context.active_action_message == 'align_yaw:dock'


def test_mission_orchestrator_advances_to_next_route_stage_before_completing() -> None:
    node = _Node()
    node.context.task_graph = [
        {'stageId': 'dock', 'title': '回桩', 'kind': 'route', 'routeName': 'dock_loop'},
        {'stageId': 'patrol', 'title': '巡检', 'kind': 'route', 'routeName': 'default'},
    ]
    node.context.task_stage_count = len(node.context.task_graph)
    node.context.current_task_stage_index = 0
    node.context.navigation_state = 'route_completed'
    node.context.navigation_route_name = 'dock_loop'
    node.context.navigation_total_goals = 2
    node.context.navigation_completed_goals = 2
    node.context.navigation_progress = 1.0

    plan = MissionOrchestrator(node).tick_tasks()

    assert plan.transition is None
    assert node.context.patrol_completed is False
    assert node.context.current_task_stage_index == 1
    assert node.context.current_task_stage_id == 'patrol'
    assert node.context.navigation_state == 'route_requested'
    assert node.context.navigation_route_name == 'default'


def test_mission_orchestrator_completes_after_non_route_terminal_stage() -> None:
    node = _Node()
    node.context.task_graph = [
        {'stageId': 'route', 'title': '巡检', 'kind': 'route', 'routeName': 'default'},
        {'stageId': 'verify', 'title': '验收', 'kind': 'verification', 'successMessage': 'mission_complete', 'verificationRules': {'requiredNavigationState': 'route_completed', 'minimumCompletedGoals': 1, 'requirePositiveProgress': True, 'requireRuntimeReady': True}},
    ]
    node.context.task_stage_count = len(node.context.task_graph)
    node.context.current_task_stage_index = 0
    node.context.navigation_state = 'route_completed'
    node.context.navigation_total_goals = 3
    node.context.navigation_completed_goals = 3
    node.context.navigation_progress = 1.0
    node.context.runtime_supervision_state = 'ready'

    plan = MissionOrchestrator(node).tick_tasks()

    assert isinstance(plan.transition, ModeTransition)
    assert plan.transition.new_mode == 'IDLE'
    assert plan.transition.reason == 'mission_complete'
    assert node.context.patrol_completed is True
    assert node.context.current_task_stage_index == 1
    assert node.context.current_task_stage_id == 'verify'



def test_mission_orchestrator_safe_stops_when_verification_stage_fails() -> None:
    node = _Node()
    node.context.task_graph = [
        {'stageId': 'route', 'title': '巡检', 'kind': 'route', 'routeName': 'default'},
        {'stageId': 'verify', 'title': '验收', 'kind': 'verification', 'successMessage': 'mission_complete', 'verificationRules': {'requiredNavigationState': 'route_completed', 'minimumCompletedGoals': 2, 'requirePositiveProgress': True, 'requireRuntimeReady': True}},
    ]
    node.context.task_stage_count = len(node.context.task_graph)
    node.context.current_task_stage_index = 0
    node.context.navigation_state = 'route_completed'
    node.context.navigation_total_goals = 1
    node.context.navigation_completed_goals = 1
    node.context.navigation_progress = 1.0
    node.context.runtime_supervision_state = 'ready'

    plan = MissionOrchestrator(node).tick_tasks()

    assert isinstance(plan.transition, ModeTransition)
    assert plan.transition.new_mode == 'SAFE_STOP'
    assert 'verification_failed' in plan.transition.reason
    assert node.context.active_action_phase == 'aborted'


def test_mission_orchestrator_verification_requires_runtime_supervision_ready() -> None:
    from robot_decision.stage_execution import start_stage
    from robot_decision.mission_context import MissionContext

    class _Node:
        def __init__(self) -> None:
            self.context = MissionContext()

    node = _Node()
    node.context.navigation_state = 'route_completed'
    node.context.navigation_completed_goals = 1
    node.context.navigation_progress = 1.0
    node.context.runtime_supervision_state = ''
    result = start_stage(node, {'kind': 'verification', 'verificationRules': {'requireRuntimeReady': True}}, current_stage_completed=True)
    assert result.status == 'failed'
    assert result.reason == 'verification_failed:runtime_supervision=missing'


def test_mission_orchestrator_safe_stops_when_stage_times_out() -> None:
    from robot_decision.mission_context import MissionContext
    from robot_decision.mission_orchestrator import MissionOrchestrator

    class _Node:
        def __init__(self) -> None:
            self.context = MissionContext()
            self.current_mode = 'PATROL'
            self.last_target = None
            self.track_manager = None

        class _Guard:
            def __enter__(self):
                return None
            def __exit__(self, exc_type, exc, tb):
                return False

        def state_guard(self):
            return self._Guard()

    node = _Node()
    orch = MissionOrchestrator(node)
    node.context.task_graph = [{'stageId': 'route_a', 'title': 'A', 'kind': 'route', 'routeName': 'r1', 'timeoutSec': 0.01}]
    node.context.current_task_stage_index = 0
    node.context.current_task_stage_id = 'route_a'
    node.context.current_task_stage_title = 'A'
    node.context.current_task_stage_timeout_sec = 0.01
    node.context.current_task_stage_started_monotonic = time.monotonic() - 0.05
    node.context.navigation_state = 'route_requested'
    plan = orch._evaluate_patrol_tick_locked()
    assert plan.transition is not None
    assert plan.transition.new_mode == 'SAFE_STOP'
    assert node.context.navigation_reason == 'stage_timeout:route_a'


def test_mission_orchestrator_start_stage_locked_sets_first_stage_timeout() -> None:
    node = _Node()
    orch = MissionOrchestrator(node)
    stage = {'stageId': 'route_a', 'title': 'A', 'kind': 'route', 'routeName': 'r1', 'timeoutSec': 5.0}
    result = orch.start_stage_locked(stage, current_stage_completed=True)
    assert result.status == 'started'
    assert node.context.current_task_stage_id == 'route_a'
    assert node.context.current_task_stage_timeout_sec == 5.0
    assert node.context.current_task_stage_started_monotonic > 0.0
    assert node.context.navigation_state == 'route_requested'
