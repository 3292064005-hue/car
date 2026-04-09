from robot_voice.command_mapper import normalize_command


def test_alias_mapping():
    assert normalize_command('开始巡检') == 'start_patrol'
    assert normalize_command('停车') == 'stop'
