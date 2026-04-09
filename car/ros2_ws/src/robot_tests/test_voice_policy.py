from robot_voice.command_policy import command_allowed, command_cooldown


def test_fault_mode_only_allows_reset_fault():
    assert command_allowed('reset_fault', 'FAULT') is True
    assert command_allowed('start_patrol', 'FAULT') is False


def test_motion_commands_have_shorter_cooldown():
    assert command_cooldown('left') < command_cooldown('start_patrol')
