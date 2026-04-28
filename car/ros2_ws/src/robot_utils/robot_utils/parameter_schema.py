from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from robot_utils.config_loader import ConfigValidationError, require_keys


@dataclass(frozen=True)
class ConfigSchema:
    name: str
    required_keys: tuple[str, ...] = ()
    optional_keys: tuple[str, ...] = ()

    @property
    def allowed_keys(self) -> set[str]:
        return set(self.required_keys) | set(self.optional_keys)


def validate_mapping(mapping: dict[str, Any], schema: ConfigSchema, *, allow_unknown: bool = True) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        raise ConfigValidationError(f"{schema.name} must be a mapping")
    require_keys(mapping, schema.required_keys, context=schema.name)
    if not allow_unknown:
        extras = sorted(set(mapping) - schema.allowed_keys)
        if extras:
            raise ConfigValidationError(f"{schema.name} unknown keys: {', '.join(extras)}")
    return mapping


PATROL_STEP_SCHEMA = ConfigSchema(
    name='patrol.step',
    required_keys=('name', 'duration_sec', 'linear'),
    optional_keys=(
        'angular', 'speak_text', 'detect_type', 'snapshot_tag', 'hold_after_sec', 'auto_track', 'done_condition',
        'timeout_action', 'on_success_next', 'on_failure_next', 'retry_limit', 'required_target_confidence',
        'allow_manual_interrupt',
    ),
)

COLOR_PROFILE_SCHEMA = ConfigSchema(
    name='vision.color_profile',
    required_keys=('h_min', 'h_max', 's_min', 's_max', 'v_min', 'v_max'),
    optional_keys=('min_area', 'stable_hits', 'lost_limit', 'confidence_floor'),
)

LAUNCH_PROFILE_SCHEMA = ConfigSchema(
    name='bringup.launch_profile',
    required_keys=('enable_voice', 'enable_vision', 'enable_monitor', 'enable_teleop'),
    optional_keys=(
        'log_level', 'use_mock_robot', 'enable_debug_overlay', 'diagnostics_enabled', 'enable_web_bridge',
        'enable_localization', 'enable_navigation', 'enable_hardware_interface', 'enable_api_server',
        'bridge_host', 'bridge_port', 'mjpeg_url', 'stream_url', 'description', 'tags', 'enable_foxglove',
        'preflight_checks_enabled', 'websocket_public_host', 'websocket_port', 'websocket_path', 'websocket_listen_host',
        'api_server_public_host', 'api_server_listen_host', 'api_server_port', 'api_server_ws_path', 'api_server_api_prefix',
    ),
)


def _ensure_bool(value: Any, *, context: str) -> None:
    if not isinstance(value, bool):
        raise ConfigValidationError(f'{context} must be a boolean')


def _ensure_string_list(value: Any, *, context: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ConfigValidationError(f'{context} must be a non-empty string list')


def _ensure_choice(value: Any, *, context: str, allowed: Iterable[str]) -> None:
    if str(value) not in set(str(item) for item in allowed):
        raise ConfigValidationError(f"{context} must be one of: {', '.join(sorted(set(str(item) for item in allowed)))}")


def _ensure_non_empty_string(value: Any, *, context: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f'{context} must be a non-empty string')




def _ensure_positive_number(value: Any, *, context: str) -> None:
    if float(value) <= 0.0:
        raise ConfigValidationError(f'{context} must be > 0')


def _ensure_non_negative_number(value: Any, *, context: str) -> None:
    if float(value) < 0.0:
        raise ConfigValidationError(f'{context} must be >= 0')


def validate_navigation_controller_params(params: dict[str, Any], *, context: str) -> dict[str, Any]:
    if 'goal_tolerance_m' in params:
        _ensure_positive_number(params.get('goal_tolerance_m'), context=f'{context}.goal_tolerance_m')
    heading_angle = float(params.get('heading_slowdown_angle_rad', 0.0) or 0.0)
    heading_legacy = float(params.get('heading_slowdown_radius_m', 0.0) or 0.0)
    if 'heading_slowdown_angle_rad' in params or 'heading_slowdown_radius_m' in params:
        if heading_angle <= 0.0 and heading_legacy <= 0.0:
            raise ConfigValidationError(f'{context}.heading_slowdown_angle_rad or {context}.heading_slowdown_radius_m must be > 0')
    if 'final_yaw_tolerance_rad' in params:
        _ensure_positive_number(params.get('final_yaw_tolerance_rad'), context=f'{context}.final_yaw_tolerance_rad')
    if 'rotate_in_place_threshold_rad' in params:
        _ensure_positive_number(params.get('rotate_in_place_threshold_rad'), context=f'{context}.rotate_in_place_threshold_rad')
    if 'max_linear_m_s' in params:
        _ensure_positive_number(params.get('max_linear_m_s'), context=f'{context}.max_linear_m_s')
    if 'max_angular_rad_s' in params:
        _ensure_positive_number(params.get('max_angular_rad_s'), context=f'{context}.max_angular_rad_s')
    if 'angular_gain' in params:
        _ensure_positive_number(params.get('angular_gain'), context=f'{context}.angular_gain')
    if 'linear_gain' in params:
        _ensure_positive_number(params.get('linear_gain'), context=f'{context}.linear_gain')
    if 'control_rate_hz' in params:
        _ensure_positive_number(params.get('control_rate_hz'), context=f'{context}.control_rate_hz')
    if 'goal_pose_terminal_yaw_enabled' in params:
        _ensure_bool(params.get('goal_pose_terminal_yaw_enabled'), context=f'{context}.goal_pose_terminal_yaw_enabled')
    return params


def validate_vision_runtime_params(params: dict[str, Any], *, context: str) -> dict[str, Any]:
    if 'poll_period' in params:
        _ensure_positive_number(params.get('poll_period'), context=f'{context}.poll_period')
    if 'snapshot_async_queue_max' in params:
        _ensure_positive_number(params.get('snapshot_async_queue_max'), context=f'{context}.snapshot_async_queue_max')
    if 'snapshot_result_drain_max' in params:
        _ensure_positive_number(params.get('snapshot_result_drain_max'), context=f'{context}.snapshot_result_drain_max')
    if 'stable_detection_hits' in params:
        _ensure_positive_number(params.get('stable_detection_hits'), context=f'{context}.stable_detection_hits')
    if 'stable_detection_misses' in params:
        _ensure_non_negative_number(params.get('stable_detection_misses'), context=f'{context}.stable_detection_misses')
    if 'tracker_max_center_jump' in params:
        _ensure_positive_number(params.get('tracker_max_center_jump'), context=f'{context}.tracker_max_center_jump')
    if 'tracker_max_area_ratio_delta' in params and float(params.get('tracker_max_area_ratio_delta')) < 1.0:
        raise ConfigValidationError(f'{context}.tracker_max_area_ratio_delta must be >= 1.0')
    if 'qrcode_cooldown_sec' in params:
        _ensure_non_negative_number(params.get('qrcode_cooldown_sec'), context=f'{context}.qrcode_cooldown_sec')
    if 'color_detection_cooldown_sec' in params:
        _ensure_non_negative_number(params.get('color_detection_cooldown_sec'), context=f'{context}.color_detection_cooldown_sec')
    if 'color_snapshot_min_interval_sec' in params:
        _ensure_non_negative_number(params.get('color_snapshot_min_interval_sec'), context=f'{context}.color_snapshot_min_interval_sec')
    if 'stream_fault_after_misses' in params:
        _ensure_positive_number(params.get('stream_fault_after_misses'), context=f'{context}.stream_fault_after_misses')
    if 'capture_reconnect_backoff_sec' in params:
        _ensure_non_negative_number(params.get('capture_reconnect_backoff_sec'), context=f'{context}.capture_reconnect_backoff_sec')
    if 'capture_reopen_after_misses' in params:
        _ensure_positive_number(params.get('capture_reopen_after_misses'), context=f'{context}.capture_reopen_after_misses')
    if 'capture_ipc_queue_max' in params:
        _ensure_positive_number(params.get('capture_ipc_queue_max'), context=f'{context}.capture_ipc_queue_max')
    return params

def validate_patrol_config(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConfigValidationError('patrol config must be a mapping')
    patrol = payload.get('patrol', payload)
    if not isinstance(patrol, dict):
        raise ConfigValidationError('patrol section must be a mapping')
    steps = patrol.get('steps')
    if not isinstance(steps, list) or not steps:
        raise ConfigValidationError('patrol.steps must be a non-empty list')
    for idx, step in enumerate(steps):
        validate_mapping(step, PATROL_STEP_SCHEMA, allow_unknown=False)
        if float(step['duration_sec']) <= 0.0:
            raise ConfigValidationError(f'patrol step[{idx}] duration_sec must be > 0')
        if 'hold_after_sec' in step and float(step['hold_after_sec']) < 0.0:
            raise ConfigValidationError(f'patrol step[{idx}] hold_after_sec must be >= 0')
        if 'retry_limit' in step and int(step['retry_limit']) < 0:
            raise ConfigValidationError(f'patrol step[{idx}] retry_limit must be >= 0')
        if 'required_target_confidence' in step:
            value = float(step['required_target_confidence'])
            if value < 0.0 or value > 1.0:
                raise ConfigValidationError(f'patrol step[{idx}] required_target_confidence must be within [0, 1]')
        if 'auto_track' in step:
            _ensure_bool(step['auto_track'], context=f'patrol step[{idx}].auto_track')
        if 'allow_manual_interrupt' in step:
            _ensure_bool(step['allow_manual_interrupt'], context=f'patrol step[{idx}].allow_manual_interrupt')
        if 'timeout_action' in step:
            _ensure_choice(step['timeout_action'], context=f'patrol step[{idx}].timeout_action', allowed=('advance', 'hold', 'abort', 'safe_stop'))
        if 'detect_type' in step and str(step['detect_type']).strip() and str(step['detect_type']) not in {'none', 'color', 'qrcode', 'color_or_qrcode', 'any'}:
            raise ConfigValidationError(f'patrol step[{idx}] detect_type invalid')
    return patrol


def validate_color_profiles(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConfigValidationError('color profile payload must be a mapping')
    profiles = payload.get('color_profiles', payload)
    if not isinstance(profiles, dict):
        raise ConfigValidationError('color_profiles must be a mapping')
    if not profiles:
        return {}
    validated: dict[str, Any] = {}
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ConfigValidationError(f'color profile {name} must be a mapping')
        validate_mapping(profile, COLOR_PROFILE_SCHEMA, allow_unknown=False)
        if float(profile.get('min_area', 0.0)) < 0.0:
            raise ConfigValidationError(f'color profile {name} min_area must be >= 0')
        validated[str(name)] = profile
    return validated


def validate_launch_profiles(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConfigValidationError('launch profile payload must be a mapping')
    profiles = payload.get('profiles', payload)
    if not isinstance(profiles, dict) or not profiles:
        raise ConfigValidationError('profiles must be a non-empty mapping')
    validated: dict[str, Any] = {}
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ConfigValidationError(f'launch profile {name} must be a mapping')
        validate_mapping(profile, LAUNCH_PROFILE_SCHEMA, allow_unknown=False)
        for key in ('enable_voice', 'enable_vision', 'enable_monitor', 'enable_teleop', 'use_mock_robot', 'enable_debug_overlay', 'diagnostics_enabled', 'enable_web_bridge', 'enable_localization', 'enable_navigation', 'enable_hardware_interface', 'enable_api_server', 'enable_foxglove', 'preflight_checks_enabled'):
            if key in profile:
                _ensure_bool(profile[key], context=f'launch profile {name}.{key}')
        if 'log_level' in profile:
            _ensure_choice(profile['log_level'], context=f'launch profile {name}.log_level', allowed=('debug', 'info', 'warn', 'error'))
        if 'description' in profile and not isinstance(profile['description'], str):
            raise ConfigValidationError(f'launch profile {name}.description must be a string')
        if 'bridge_host' in profile:
            _ensure_non_empty_string(profile['bridge_host'], context=f'launch profile {name}.bridge_host')
        if 'bridge_port' in profile and int(profile['bridge_port']) <= 0:
            raise ConfigValidationError(f'launch profile {name}.bridge_port must be > 0')
        if 'mjpeg_url' in profile and profile['mjpeg_url'] is not None:
            _ensure_non_empty_string(profile['mjpeg_url'], context=f'launch profile {name}.mjpeg_url')
        if 'stream_url' in profile and profile['stream_url'] is not None:
            _ensure_non_empty_string(profile['stream_url'], context=f'launch profile {name}.stream_url')
        if 'websocket_public_host' in profile and profile['websocket_public_host'] is not None:
            _ensure_non_empty_string(profile['websocket_public_host'], context=f'launch profile {name}.websocket_public_host')
        if 'websocket_listen_host' in profile and profile['websocket_listen_host'] is not None:
            _ensure_non_empty_string(profile['websocket_listen_host'], context=f'launch profile {name}.websocket_listen_host')
        if 'websocket_port' in profile and int(profile['websocket_port']) <= 0:
            raise ConfigValidationError(f'launch profile {name}.websocket_port must be > 0')
        if 'websocket_path' in profile and profile['websocket_path'] is not None:
            _ensure_non_empty_string(profile['websocket_path'], context=f'launch profile {name}.websocket_path')
            if not str(profile['websocket_path']).startswith('/'):
                raise ConfigValidationError(f'launch profile {name}.websocket_path must start with /')
        if 'api_server_port' in profile and int(profile['api_server_port']) <= 0:
            raise ConfigValidationError(f'launch profile {name}.api_server_port must be > 0')
        if 'api_server_ws_path' in profile and profile['api_server_ws_path'] is not None:
            _ensure_non_empty_string(profile['api_server_ws_path'], context=f'launch profile {name}.api_server_ws_path')
            if not str(profile['api_server_ws_path']).startswith('/'):
                raise ConfigValidationError(f'launch profile {name}.api_server_ws_path must start with /')
        if 'api_server_api_prefix' in profile and profile['api_server_api_prefix'] is not None:
            _ensure_non_empty_string(profile['api_server_api_prefix'], context=f'launch profile {name}.api_server_api_prefix')
            if not str(profile['api_server_api_prefix']).startswith('/'):
                raise ConfigValidationError(f'launch profile {name}.api_server_api_prefix must start with /')
        if (
            'mjpeg_url' in profile and 'stream_url' in profile
            and profile['mjpeg_url'] is not None and profile['stream_url'] is not None
            and str(profile['mjpeg_url']).strip() != str(profile['stream_url']).strip()
        ):
            raise ConfigValidationError(f'launch profile {name} mjpeg_url and stream_url must resolve to the same endpoint when both are provided')
        if 'tags' in profile:
            _ensure_string_list(profile['tags'], context=f'launch profile {name}.tags')
        validated[str(name)] = profile
    return validated


def validate_ros_params(payload: Any, node_name: str, required: Iterable[str] = ()) -> dict[str, Any]:
    if not isinstance(payload, dict) or node_name not in payload:
        raise ConfigValidationError(f'{node_name} root section missing')
    node = payload[node_name]
    if not isinstance(node, dict) or 'ros__parameters' not in node:
        raise ConfigValidationError(f'{node_name}.ros__parameters missing')
    params = node['ros__parameters']
    if not isinstance(params, dict):
        raise ConfigValidationError(f'{node_name}.ros__parameters must be a mapping')
    require_keys(params, required, context=f'{node_name}.ros__parameters')
    return params


def validate_launch_profile_name(name: str, supported: Iterable[str]) -> str:
    value = str(name).strip()
    if not value:
        raise ConfigValidationError('launch profile name must be non-empty')
    allowed = tuple(sorted(set(str(item) for item in supported)))
    if value not in allowed:
        raise ConfigValidationError(f'unsupported launch profile: {value}')
    return value
