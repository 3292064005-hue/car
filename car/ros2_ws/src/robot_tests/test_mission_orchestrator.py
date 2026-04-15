from __future__ import annotations

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
