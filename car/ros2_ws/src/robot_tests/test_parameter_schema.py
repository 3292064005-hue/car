from pathlib import Path

import pytest

from robot_utils.config_loader import ConfigValidationError, load_structured_file
from robot_utils.parameter_schema import (
    validate_color_profiles,
    validate_launch_profile_name,
    validate_navigation_controller_params,
    validate_patrol_config,
    validate_ros_params,
    validate_vision_runtime_params,
)


def test_validate_patrol_config_accepts_inline_payload():
    patrol = validate_patrol_config({'patrol': {'steps': [{'name': 'scan_a', 'duration_sec': 1.0, 'linear': 0.0, 'angular': 0.5}]}})
    assert patrol['steps'][0]['name'] == 'scan_a'


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



def test_validate_navigation_controller_params_rejects_invalid_pose_goal_terminal_yaw_flag():
    with pytest.raises(ConfigValidationError):
        validate_navigation_controller_params({
            'goal_tolerance_m': 0.18,
            'heading_slowdown_angle_rad': 1.2,
            'heading_slowdown_radius_m': 1.2,
            'final_yaw_tolerance_rad': 0.12,
            'rotate_in_place_threshold_rad': 0.7,
            'max_linear_m_s': 0.26,
            'max_angular_rad_s': 1.1,
            'angular_gain': 1.6,
            'linear_gain': 0.8,
            'control_rate_hz': 10.0,
            'goal_pose_terminal_yaw_enabled': 'yes',
        }, context='robot_navigation.ros__parameters')


def test_validate_navigation_controller_params_accepts_compatibility_guard_flag():
    validated = validate_navigation_controller_params({
        'goal_tolerance_m': 0.18,
        'heading_slowdown_angle_rad': 1.2,
        'heading_slowdown_radius_m': 1.2,
        'final_yaw_tolerance_rad': 0.12,
        'rotate_in_place_threshold_rad': 0.7,
        'max_linear_m_s': 0.26,
        'max_angular_rad_s': 1.1,
        'angular_gain': 1.6,
        'linear_gain': 0.8,
        'control_rate_hz': 10.0,
        'goal_pose_terminal_yaw_enabled': False,
    }, context='robot_navigation.ros__parameters')
    assert validated['goal_pose_terminal_yaw_enabled'] is False


def test_validate_vision_runtime_params_rejects_invalid_tracker_ratio_delta():
    with pytest.raises(ConfigValidationError):
        validate_vision_runtime_params({
            'poll_period': 0.1,
            'snapshot_async_queue_max': 16,
            'snapshot_result_drain_max': 8,
            'stable_detection_hits': 2,
            'stable_detection_misses': 3,
            'tracker_max_center_jump': 0.35,
            'tracker_max_area_ratio_delta': 0.8,
            'qrcode_cooldown_sec': 2.0,
            'color_detection_cooldown_sec': 1.0,
            'color_snapshot_min_interval_sec': 2.0,
            'stream_fault_after_misses': 10,
            'capture_reconnect_backoff_sec': 0.5,
            'capture_reopen_after_misses': 5,
            'capture_ipc_queue_max': 1,
        }, context='robot_vision.ros__parameters')
