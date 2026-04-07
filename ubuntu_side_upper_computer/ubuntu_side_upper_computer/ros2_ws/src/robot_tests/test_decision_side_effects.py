from __future__ import annotations

import json
from types import SimpleNamespace

from builtin_interfaces.msg import Time
from robot_decision.decision_policy import EffectPlan, EventEffect, SpeakEffect
from robot_decision.decision_side_effects import DecisionSideEffects
from robot_decision.mission_context import MissionContext


class _Publisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, msg) -> None:
        self.messages.append(msg)


class _Clock:
    class _Now:
        def __init__(self) -> None:
            self.nanoseconds = 0

        def to_msg(self):
            return Time()

    def now(self):
        return self._Now()


class _Node:
    def __init__(self) -> None:
        self.current_mode = 'IDLE'
        self.previous_mode = 'BOOT'
        self.context = MissionContext(last_transition_reason='boot_complete')
        self.mode_pub = _Publisher()
        self.event_pub = _Publisher()
        self.speak_pub = _Publisher()
        self.snapshot_pub = _Publisher()
        self.summary_pub = _Publisher()
        self.runtime_param_apply_pub = _Publisher()
        self.action_runtime = SimpleNamespace(notify_state_change=lambda: None)
        self.mode_guard = SimpleNamespace(
            safe_stop_recovery_status=lambda require_manual_confirm=False: (True, None),
            command_context=lambda: SimpleNamespace(),
            system_ready_for_patrol=lambda: True,
            manual_recovery_required=lambda: False,
        )

    def state_guard(self):
        class _Guard:
            def __enter__(self_inner):
                return None

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Guard()

    def get_clock(self):
        return _Clock()

    def get_name(self) -> str:
        return 'decision_test_node'


def test_side_effects_emit_effect_plan_publishes_all_effect_types(monkeypatch) -> None:
    monkeypatch.setattr('robot_decision.decision_projection.command_capability_snapshot', lambda ctx: {'allowedTargetModes': [], 'modeReasons': {}, 'commandPermissions': {}})
    node = _Node()
    effects = DecisionSideEffects(node=node)
    plan = EffectPlan(
        events=[EventEffect('decision', 'info', 'ok')],
        speaks=[SpeakEffect('boot_ok', 1)],
        snapshots=['snapshot:test'],
    )
    effects.emit_effect_plan(plan)
    assert node.event_pub.messages
    assert node.speak_pub.messages
    assert node.snapshot_pub.messages[0].data == 'snapshot:test'


def test_side_effects_publish_runtime_param_apply_result_serializes_json() -> None:
    node = _Node()
    effects = DecisionSideEffects(node=node)
    effects.publish_runtime_param_apply_result({'consumer': 'robot_decision', 'transaction_id': 'txn', 'runtime_param_version': 1, 'ok': True, 'message': 'ok', 'ts': '', 'trace_id': ''})
    assert json.loads(node.runtime_param_apply_pub.messages[0].data)['transaction_id'] == 'txn'
