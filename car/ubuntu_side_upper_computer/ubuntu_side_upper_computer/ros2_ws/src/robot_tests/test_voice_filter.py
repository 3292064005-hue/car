from robot_voice.command_filter import CommandFilterState, should_accept


def test_debounce():
    state = CommandFilterState()
    assert should_accept('start_patrol', state, 1.0)
    assert not should_accept('start_patrol', state, 1.0)
