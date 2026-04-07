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

from robot_bringup.config_resolution import resolve_bringup_config
from robot_bringup.dependency_matrix import dependency_plan_for
from robot_bringup.launch_profiles import get_launch_profile, supported_profiles
from robot_bringup.preflight import build_preflight_report
from robot_bridge.runtime_factory import runtime_policy_snapshot



def build_report(profile_name: str, *, config_path: str | None = None) -> dict[str, object]:
    profile = get_launch_profile(profile_name, config_path=config_path)
    resolved = resolve_bringup_config(config_path)
    config_dir = resolved.config_root
    return {
        'profile': profile.to_dict(),
        'supported_profiles': list(supported_profiles(config_path=config_path)),
        'config_dir': str(config_dir),
        'config_files': sorted(path.name for path in config_dir.glob('*.yaml')),
        'required_configs': ['bridge.yaml', 'control.yaml', 'decision.yaml', 'monitor.yaml', 'vision.yaml', 'voice.yaml', 'patrol.yaml', 'fault.yaml'],
        'config_resolution': {
            'config_root': str(resolved.config_root),
            'launch_profiles_path': str(resolved.launch_profiles_path),
            'raw_input': resolved.raw_input,
            'source': resolved.source,
        },
        'dependency_plan': dependency_plan_for(profile, surface='backend').to_dict(),
        'runtime_policy': runtime_policy_snapshot(),
        'hardware_boundary': {
            'launch_profile_requires_real_robot': not profile.use_mock_robot,
            'board_validation_scope': 'ubuntu_side_launch_and_dependency_checks_only',
            'board_validation_performed_by_report': False,
        },
        'preflight': build_preflight_report(profile_name, config_path=config_path),
    }



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render effective launch profile report')
    parser.add_argument('profile', nargs='?', default='full')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--output', default='-', help='Output path, or - for stdout')
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    report = build_report(args.profile, config_path=args.config_path)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output == '-':
        print(payload)
    else:
        Path(args.output).write_text(payload, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
