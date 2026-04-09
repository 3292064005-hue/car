from robot_decision.recovery_policy import can_recover_from_safe_stop, recovery_summary


class FaultStub:
    def __init__(self, level: str):
        self.level = level


def test_recovery_blocked_by_estop():
    assert not can_recover_from_safe_stop(estop_active=True, link_ok=True, last_fault=None)
    assert recovery_summary(True, True, None) == 'estop_active'


def test_recovery_blocked_by_fatal_fault():
    assert not can_recover_from_safe_stop(estop_active=False, link_ok=True, last_fault=FaultStub('fatal'))
