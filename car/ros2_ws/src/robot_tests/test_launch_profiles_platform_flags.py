from robot_bringup.launch_profiles import get_launch_profile, supported_profiles


def test_mock_profile_enables_platform_stack() -> None:
    profile = get_launch_profile('mock')
    assert profile.enable_localization is True
    assert profile.enable_navigation is True
    assert profile.enable_hardware_interface is True
    assert profile.enable_api_server is True


def test_sim_profile_is_supported() -> None:
    assert 'sim' in supported_profiles()
