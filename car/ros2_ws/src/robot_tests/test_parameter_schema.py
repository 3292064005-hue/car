from pathlib import Path

import pytest

from robot_utils.config_loader import ConfigValidationError, load_structured_file
from robot_utils.parameter_schema import (
    validate_color_profiles,
    validate_launch_profile_name,
    validate_patrol_config,
    validate_ros_params,
)


def test_validate_patrol_config_accepts_repo_file():
    path = Path(__file__).resolve().parents[1] / 'robot_bringup' / 'config' / 'patrol.yaml'
    data = load_structured_file(str(path), {})
    patrol = validate_patrol_config(data)
    assert patrol['steps'][0]['name']


def test_validate_color_profiles_rejects_missing_hsv():
    with pytest.raises(ConfigValidationError):
        validate_color_profiles({'color_profiles': {'red': {'h_min': 1}}})


def test_validate_ros_params_rejects_missing_parameters():
    with pytest.raises(ConfigValidationError):
        validate_ros_params({}, 'robot_control', required=('max_linear',))


def test_validate_launch_profile_name_rejects_unknown():
    try:
        validate_launch_profile_name('weird', ('dev', 'demo'))
    except Exception as exc:
        assert 'unsupported launch profile' in str(exc)
    else:
        raise AssertionError('expected validation error')


def test_launch_profile_stream_alias_and_conflict():
    from robot_utils.parameter_schema import validate_launch_profiles
    payload = {'profiles': {'demo': {'enable_voice': True, 'enable_vision': True, 'enable_monitor': True, 'enable_teleop': False, 'stream_url': 'http://10.0.0.2/stream'}}}
    assert validate_launch_profiles(payload)['demo']['stream_url'] == 'http://10.0.0.2/stream'


def test_launch_profile_websocket_fields_validate() -> None:
    from robot_utils.parameter_schema import validate_launch_profiles
    payload = {'profiles': {'mock': {'enable_voice': True, 'enable_vision': True, 'enable_monitor': True, 'enable_teleop': True, 'websocket_public_host': '10.0.0.8', 'websocket_listen_host': '0.0.0.0', 'websocket_port': 9102, 'websocket_path': '/robot/ws'}}}
    validated = validate_launch_profiles(payload)
    assert validated['mock']['websocket_public_host'] == '10.0.0.8'


def test_launch_profile_websocket_path_must_start_with_slash() -> None:
    from robot_utils.parameter_schema import validate_launch_profiles
    with pytest.raises(ConfigValidationError):
        validate_launch_profiles({'profiles': {'mock': {'enable_voice': True, 'enable_vision': True, 'enable_monitor': True, 'enable_teleop': True, 'websocket_path': 'robot/ws'}}})
