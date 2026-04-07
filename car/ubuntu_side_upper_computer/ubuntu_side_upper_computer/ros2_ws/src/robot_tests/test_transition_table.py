from robot_decision.transition_rules import transition_requires_manual_ack, transition_table


def test_transition_table_contains_safe_stop_guard() -> None:
    table = transition_table()
    safe_stop = next(item for item in table if item['mode'] == 'SAFE_STOP')
    assert safe_stop['requires_manual_ack'] is True
    assert 'IDLE' in safe_stop['allowed_targets']
    assert transition_requires_manual_ack('SAFE_STOP') is True
