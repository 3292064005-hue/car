from robot_decision.transition_rules import can_transition
from robot_utils.constants import MODE_BOOT, MODE_FAULT, MODE_IDLE, MODE_PATROL, MODE_TRACK


def test_boot_can_only_go_idle_or_fault():
    assert can_transition(MODE_BOOT, MODE_IDLE)
    assert can_transition(MODE_BOOT, MODE_FAULT)
    assert not can_transition(MODE_BOOT, MODE_TRACK)


def test_patrol_can_enter_track():
    assert can_transition(MODE_PATROL, MODE_TRACK)
