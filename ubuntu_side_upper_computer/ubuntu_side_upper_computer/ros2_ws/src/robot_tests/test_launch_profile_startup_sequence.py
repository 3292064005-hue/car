from robot_bringup.launch_profiles import get_launch_profile


def test_profile_startup_sequence_matches_p0_p1_order() -> None:
    profile = get_launch_profile('hardware')
    assert profile.startup_sequence() == ('contracts', 'bridge', 'control', 'monitor', 'vision_voice', 'decision', 'frontend')
