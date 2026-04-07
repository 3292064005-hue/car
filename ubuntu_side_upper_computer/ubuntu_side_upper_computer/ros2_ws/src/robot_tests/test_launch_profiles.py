def teardown_function(_func=None):
    reset_launch_profile_cache()


from robot_bringup.launch_profiles import get_launch_profile, reset_launch_profile_cache, supported_profiles
from robot_utils.parameter_schema import validate_launch_profiles


def test_supported_profiles_cover_expected_names():
    names = set(supported_profiles())
    assert {'minimal', 'dev', 'demo', 'full'}.issubset(names)


def test_get_launch_profile_returns_defaults():
    profile = get_launch_profile('demo')
    assert profile.enable_monitor is True
    assert profile.enable_teleop is False


def test_validate_launch_profiles_accepts_minimal_payload():
    payload = {'profiles': {'dev': {'enable_voice': True, 'enable_vision': True, 'enable_monitor': True, 'enable_teleop': True}}}
    validated = validate_launch_profiles(payload)
    assert 'dev' in validated


def test_get_launch_profile_includes_websocket_defaults() -> None:
    profile = get_launch_profile('mock')
    assert profile.websocket_port == 9001
    assert profile.websocket_path == '/ws'
