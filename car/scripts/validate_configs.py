#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_api_server.api_server_main import _load_config_defaults


def _load_bridge_session_defaults(config_file: str) -> dict[str, object]:
    path = Path(config_file)
    payload = load_structured_file(str(path), {})
    config = payload.get('robot_bridge', payload) if isinstance(payload, dict) else {}
    params = config.get('ros__parameters', {}) if isinstance(config, dict) and isinstance(config.get('ros__parameters', {}), dict) else {}
    tokens = params.get('operator_tokens', [])
    if not isinstance(tokens, list):
        raise ConfigValidationError('robot_bridge.operator_tokens must be a list')
    return {
        'default_role': str(params.get('default_session_role', 'observer')).strip() or 'observer',
        'require_operator_token': bool(params.get('require_operator_token', True)),
        'operator_tokens': [str(item).strip() for item in tokens if str(item).strip()],
        'internal_command_socket_path': str(params.get('internal_command_socket_path', '/tmp/inspection_robot/bridge_internal_command.sock')).strip() or '/tmp/inspection_robot/bridge_internal_command.sock',
    }
from robot_bringup.config_resolution import resolve_bringup_config
from robot_description.description_model import normalize_description_payload, packaged_xacro_matches_description
from robot_utils.config_loader import ConfigValidationError, load_structured_file
from robot_utils.parameter_schema import (
    validate_color_profiles,
    validate_launch_profiles,
    validate_ros_params,
)



def validate_file(path: Path) -> tuple[bool, str]:
    data = load_structured_file(str(path), {})
    try:
        name = path.name
        if name == 'launch_profiles.yaml':
            validate_launch_profiles(data)
        elif name == 'vision.yaml':
            validate_ros_params(data, 'robot_vision', required=('stream_url', 'poll_period', 'snapshot_dir', 'enable_debug_overlay', 'capture_process_enabled', 'capture_ipc_queue_max'))
        elif name == 'bridge.yaml':
            validate_ros_params(data, 'robot_bridge', required=('host', 'port', 'heartbeat_period'))
            bridge_auth = _load_bridge_session_defaults(str(path))
            default_role = str(bridge_auth.get('default_role', 'observer')).strip().lower()
            if default_role not in {'operator', 'observer', 'readonly'}:
                raise ConfigValidationError('robot_bridge.default_session_role must be operator/observer/readonly')
        elif name == 'control.yaml':
            validate_ros_params(data, 'robot_control', required=('max_linear', 'max_angular', 'publish_rate_hz'))
        elif name == 'decision.yaml':
            validate_ros_params(
                data,
                'robot_decision',
                required=('track_lost_limit', 'auto_track_on_target', 'decision_intent_queue_max', 'decision_intent_batch_max'),
            )
        elif name == 'voice.yaml':
            validate_ros_params(data, 'robot_voice', required=('debounce_sec', 'raw_cmd_topic', 'accepted_cmd_topic', 'ingress_health_topic', 'ingress_timeout_sec'))
        elif name == 'monitor.yaml':
            validate_ros_params(
                data,
                'robot_monitor',
                required=(
                    'summary_period',
                    'event_log_path',
                    'metrics_path',
                    'diagnostics_enabled',
                    'lifecycle_manager_status_topic',
                    'voice_ingress_health_topic',
                ),
            )
        elif name == 'lifecycle_manager.yaml':
            validate_ros_params(data, 'robot_lifecycle_manager', required=('autostart', 'managed_nodes', 'bond_topic', 'status_topic', 'ready_topic'))
        elif name == 'fault.yaml':
            validate_ros_params(data, 'robot_control')
            validate_ros_params(data, 'robot_bridge')
        elif name == 'description.yaml':
            normalize_description_payload(data)
            if not packaged_xacro_matches_description():
                raise ConfigValidationError('robot_description xacro is out of sync with description.yaml')
        elif name == 'api_server.yaml':
            defaults = _load_config_defaults(str(path))
            if not defaults['listen_host']:
                raise ConfigValidationError('robot_api_server.listen_host must be non-empty')
            if int(defaults['listen_port']) <= 0:
                raise ConfigValidationError('robot_api_server.listen_port must be > 0')
            if not str(defaults['ws_path']).startswith('/'):
                raise ConfigValidationError('robot_api_server.ws_path must start with /')
            if not str(defaults['api_prefix']).startswith('/'):
                raise ConfigValidationError('robot_api_server.api_prefix must start with /')
            auth = defaults.get('auth', {})
            if not isinstance(auth, dict):
                raise ConfigValidationError('robot_api_server.auth must be a mapping')
            default_role = str(auth.get('default_role', 'operator')).strip().lower()
            if default_role not in {'operator', 'observer', 'readonly'}:
                raise ConfigValidationError('robot_api_server.auth.default_role must be operator/observer/readonly')
            operator_tokens = auth.get('operator_tokens', [])
            if not isinstance(operator_tokens, list):
                raise ConfigValidationError('robot_api_server.auth.operator_tokens must be a list')
            upstream = auth.get('upstream_bridge_session', {}) if isinstance(auth.get('upstream_bridge_session', {}), dict) else {}
            internal_command_socket_path = str(upstream.get('internal_command_socket_path', '')).strip()
            if not internal_command_socket_path:
                raise ConfigValidationError('robot_api_server.auth.upstream_bridge_session.internal_command_socket_path must be non-empty')
            bridge_path = path.parent / 'bridge.yaml'
            if bridge_path.is_file():
                bridge_auth = _load_bridge_session_defaults(str(bridge_path))
                if bool(bridge_auth.get('require_operator_token', True)) != bool(auth.get('require_operator_token', True)):
                    raise ConfigValidationError('bridge/api operator token requirements must match')
                if sorted(bridge_auth.get('operator_tokens', [])) != sorted(operator_tokens):
                    raise ConfigValidationError('bridge/api operator tokens must stay in sync')
                if internal_command_socket_path != str(bridge_auth.get('internal_command_socket_path', '') or ''):
                    raise ConfigValidationError('bridge/api internal_command_socket_path must stay in sync')
        color_profile_raw = str(data.get('robot_vision', {}).get('ros__parameters', {}).get('color_profile_path', '')).strip()
        if color_profile_raw:
            color_profile = Path(color_profile_raw)
            if not color_profile.is_absolute():
                color_profile = (path.parent / color_profile).resolve()
            if color_profile.exists() and color_profile.is_file():
                validate_color_profiles(load_structured_file(str(color_profile), {}))
    except ConfigValidationError as exc:
        return False, str(exc)
    return True, 'ok'



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Validate bringup configuration files')
    parser.add_argument('--config-path', default=None, help='Bringup config directory or launch_profiles.yaml path')
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    resolved = resolve_bringup_config(args.config_path)
    config_dir = resolved.config_root
    failures = []
    for path in sorted(config_dir.glob('*.yaml')):
        ok, msg = validate_file(path)
        status = 'OK' if ok else 'ERR'
        print(f'[{status}] {path.name}: {msg}')
        if not ok:
            failures.append(path.name)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
