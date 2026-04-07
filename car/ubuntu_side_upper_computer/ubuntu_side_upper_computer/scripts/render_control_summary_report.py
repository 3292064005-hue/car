#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_bringup.config_resolution import resolve_config_file
from robot_utils.config_loader import load_structured_file
from robot_utils.constants import MODE_PRIORITY



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render control summary report')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--output', default='-')
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    config_path = resolve_config_file('control.yaml', args.config_path)
    params = load_structured_file(config_path, {})['robot_control']['ros__parameters']
    report = {
        'control_config_path': str(config_path),
        'source_priority': ['FAULT/SAFE_STOP', 'MANUAL', 'TRACK', 'PATROL', 'IDLE'],
        'mode_priority_reference': MODE_PRIORITY,
        'limits': {
            'max_linear': params['max_linear'],
            'reverse_max_linear': params['reverse_max_linear'],
            'max_angular': params['max_angular'],
            'turn_slowdown_ratio': params['turn_slowdown_ratio'],
            'track_linear_scale': params['track_linear_scale'],
            'track_angular_scale': params['track_angular_scale'],
        },
        'timeouts_sec': {
            'manual': params['manual_timeout_sec'],
            'patrol': params['patrol_timeout_sec'],
            'track': params['track_timeout_sec'],
        },
        'ramp': {
            'max_linear_step': params['max_linear_step'],
            'max_angular_step': params['max_angular_step'],
            'resume_linear_step': params['resume_linear_step'],
            'resume_angular_step': params['resume_angular_step'],
        },
        'power_guard': {
            'low_power_linear_scale': params['low_power_linear_scale'],
            'low_power_angular_scale': params['low_power_angular_scale'],
        },
        'summary_fields': ['mode', 'source', 'selected_age_sec', 'chassis_age_sec', 'power_age_sec', 'safety_latched', 'safety_reason', 'fault_hold_active', 'power_limited', 'power_reason', 'vx', 'wz', 'track_mode'],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output == '-':
        print(text)
    else:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
