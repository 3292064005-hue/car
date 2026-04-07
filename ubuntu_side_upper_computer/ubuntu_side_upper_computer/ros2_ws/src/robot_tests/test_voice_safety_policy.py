from robot_voice.command_policy import command_allowed


def test_resume_requires_safe_stop_recoverable() -> None:
    assert command_allowed('resume_from_safe_stop', 'SAFE_STOP', safe_stop_recoverable=False) is False
    assert command_allowed('resume_from_safe_stop', 'SAFE_STOP', safe_stop_recoverable=True) is True
    assert command_allowed('forward', 'IDLE') is False


def test_start_patrol_requires_idle_ready() -> None:
    assert command_allowed('start_patrol', 'IDLE', ready_for_patrol=True) is True
    assert command_allowed('start_patrol', 'IDLE', ready_for_patrol=False) is False
    assert command_allowed('start_patrol', 'MANUAL', ready_for_patrol=True) is False
    assert command_allowed('resume_from_safe_stop', 'IDLE', safe_stop_recoverable=True) is False
