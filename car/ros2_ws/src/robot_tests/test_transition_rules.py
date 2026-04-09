from robot_decision.transition_rules import explain_transition
from robot_utils.constants import MODE_BOOT, MODE_TRACK


def test_transition_reason_exposes_allowed_targets():
    reason = explain_transition(MODE_BOOT, MODE_TRACK)
    assert 'not allowed' in reason
    assert 'IDLE' in reason
