from __future__ import annotations

from types import SimpleNamespace

from robot_msgs.msg import Fault, VisionTarget, VoiceCommand
from robot_decision.decision_policy import DecisionPolicy
from robot_decision.mission_context import MissionContext
from robot_utils.constants import FAULT_LEVEL_FATAL, MODE_PATROL, MODE_TRACK, VOICE_CMD_START_PATROL


class _Param:
    def __init__(self, value):
        self.value = value


class _Node:
    def __init__(self) -> None:
        self.current_mode = MODE_PATROL
        self.context = MissionContext(patrol_started=True, patrol_completed=False, lost_target_count=2)
        self.last_fault = None
        self.system_status = None
        self.chassis_state = None
        self._safe_stop_manual_confirmed = False
        self.patrol_manager = SimpleNamespace(manual_interrupt_allowed=lambda: True)
        self._params = {
            'snapshot_on_fault': True,
            'auto_track_on_target': True,
            'target_confidence_min': 0.55,
            'track_lost_limit': 3,
            'snapshot_on_target': True,
            'snapshot_on_qrcode': True,
            'safe_stop_on_wifi_loss': True,
            'require_ready_for_patrol': True,
        }

    def get_parameter(self, name: str):
        return _Param(self._params[name])


def test_policy_fault_fatal_requests_fault_mode_and_snapshot() -> None:
    policy = DecisionPolicy(node=_Node())
    decision = policy.evaluate_fault(Fault(code='FATAL', level=FAULT_LEVEL_FATAL, description='boom'))
    assert decision.transition is not None
    assert decision.transition.new_mode == 'FAULT'
    assert decision.effect_plan.snapshots == ['fault']
    assert decision.effect_plan.speaks[0].text == 'fault_fatal'


def test_policy_voice_start_patrol_routes_to_mode_transition() -> None:
    node = _Node()
    node.current_mode = 'IDLE'
    policy = DecisionPolicy(node=node)
    decision = policy.evaluate_voice_command(VoiceCommand(command=VOICE_CMD_START_PATROL))
    assert decision.transition is not None
    assert decision.transition.new_mode == 'PATROL'


def test_policy_target_loss_requests_exit_from_track() -> None:
    node = _Node()
    node.current_mode = MODE_TRACK
    policy = DecisionPolicy(node=node)
    decision = policy.evaluate_target(VisionTarget(detected=False, confidence=0.0, target_type='color'))
    assert decision.transition is not None
    assert decision.transition.reason == 'track_target_lost'
