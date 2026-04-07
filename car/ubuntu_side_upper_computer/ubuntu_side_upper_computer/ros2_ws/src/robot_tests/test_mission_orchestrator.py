from __future__ import annotations

from types import SimpleNamespace

from geometry_msgs.msg import Twist
from robot_decision.decision_policy import ModeTransition
from robot_decision.mission_context import MissionContext
from robot_decision.mission_orchestrator import MissionOrchestrator
from robot_utils.constants import MODE_PATROL


class _Param:
    def __init__(self, value):
        self.value = value


class _Clock:
    class _Now:
        def __init__(self) -> None:
            self.nanoseconds = 0
    def now(self):
        return self._Now()


class _PatrolManager:
    def __init__(self) -> None:
        self.current_index = 1
    def update(self, now_sec: float):
        del now_sec
        cmd = Twist()
        cmd.linear.x = 0.2
        step = SimpleNamespace(name='step1', snapshot_tag='tag1')
        return SimpleNamespace(cmd=cmd, step=step, finished=False, step_completed=True, speak_text='hello', transition_action='safe_stop', transition_reason='step_timeout_safe_stop')
    def progress_ratio(self, now_sec: float) -> float:
        del now_sec
        return 0.5
    def step_descriptor(self):
        return {'retry_count': 0, 'retry_limit': 0}
    def is_finished(self) -> bool:
        return False


class _Node:
    def __init__(self) -> None:
        self.current_mode = MODE_PATROL
        self.context = MissionContext()
        self.patrol_manager = _PatrolManager()
        self.track_manager = SimpleNamespace(compute_cmd=lambda target: Twist())
        self.last_target = None
    def state_guard(self):
        class _Guard:
            def __enter__(self): return None
            def __exit__(self, exc_type, exc, tb): return False
        return _Guard()
    def get_clock(self):
        return _Clock()


def test_mission_orchestrator_returns_plan_without_publishing_side_effects() -> None:
    node = _Node()
    plan = MissionOrchestrator(node).tick_tasks()
    assert plan.patrol_cmd is not None
    assert plan.effect_plan.speaks[0].text == 'hello'
    assert plan.effect_plan.snapshots == ['tag1']
    assert isinstance(plan.transition, ModeTransition)
    assert plan.transition.new_mode == 'SAFE_STOP'
