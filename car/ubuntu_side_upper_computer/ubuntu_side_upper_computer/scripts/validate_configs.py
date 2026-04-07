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

from robot_bringup.config_resolution import resolve_bringup_config
from robot_utils.config_loader import ConfigValidationError, load_structured_file
from robot_utils.parameter_schema import (
    validate_color_profiles,
    validate_launch_profiles,
    validate_patrol_config,
    validate_ros_params,
)



def validate_file(path: Path) -> tuple[bool, str]:
    data = load_structured_file(str(path), {})
    try:
        name = path.name
        if name == 'patrol.yaml':
            validate_patrol_config(data)
        elif name == 'launch_profiles.yaml':
            validate_launch_profiles(data)
        elif name == 'vision.yaml':
            validate_ros_params(data, 'robot_vision', required=('stream_url', 'poll_period', 'snapshot_dir', 'enable_debug_overlay', 'capture_process_enabled', 'capture_ipc_queue_max'))
        elif name == 'bridge.yaml':
            validate_ros_params(data, 'robot_bridge', required=('host', 'port', 'heartbeat_period'))
        elif name == 'control.yaml':
            validate_ros_params(data, 'robot_control', required=('max_linear', 'max_angular', 'publish_rate_hz'))
        elif name == 'decision.yaml':
            validate_ros_params(
                data,
                'robot_decision',
                required=('track_lost_limit', 'auto_track_on_target', 'decision_intent_queue_max', 'decision_intent_batch_max'),
            )
        elif name == 'voice.yaml':
            validate_ros_params(data, 'robot_voice', required=('debounce_sec',))
        elif name == 'monitor.yaml':
            validate_ros_params(data, 'robot_monitor', required=('summary_period', 'event_log_path', 'metrics_path', 'diagnostics_enabled'))
        elif name == 'fault.yaml':
            validate_ros_params(data, 'robot_control')
            validate_ros_params(data, 'robot_bridge')
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
