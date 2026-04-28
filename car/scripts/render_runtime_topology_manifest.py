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
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

from robot_bringup.launch_profiles import get_launch_profile
from robot_bringup.matrix_contracts import startup_sequence_for_profile
from robot_bridge.runtime_factory import runtime_policy_snapshot
from robot_contracts.lane_registry import lane_registry_payload
from resolve_runtime_surface_config import build_payload as build_surface_payload
from runtime_surface_inventory import runtime_signal_matrix_payload


def build_manifest(profile_name: str, config_path: str | None = None) -> dict[str, object]:
    profile = get_launch_profile(profile_name, config_path=config_path)
    startup_sequence = list(startup_sequence_for_profile(profile, config_path=config_path))
    if 'frontend' in startup_sequence and 'operator_phase' not in startup_sequence:
        startup_sequence.append('operator_phase')
    lane_registry = lane_registry_payload(include_experimental=True)
    return {
        'status': 'ok',
        'profile': profile_name,
        'reportScope': 'runtime_topology_manifest',
        'startupSequence': startup_sequence,
        'runtimePolicy': runtime_policy_snapshot(),
        'defaultVisibleLanes': sorted([key for key, entry in lane_registry.items() if entry['defaultSurfaceExposure'] == 'default_visible']),
        'hiddenByDefaultLanes': sorted([key for key, entry in lane_registry.items() if entry['defaultSurfaceExposure'] == 'hidden_by_default']),
        'surfaces': {
            'frontend': build_surface_payload(profile_name=profile_name, surface='frontend', config_path=config_path),
            'backend': build_surface_payload(profile_name=profile_name, surface='backend', config_path=config_path),
            'web_bridge': build_surface_payload(profile_name=profile_name, surface='web_bridge', config_path=config_path),
        },
        'signalMatrix': runtime_signal_matrix_payload(profile_name, config_path=config_path),
        'authorityChain': ['frontend', 'robot_api_server', 'robot_web_bridge', 'robot_decision_or_robot_control', 'robot_bridge'],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Render runtime topology manifest.')
    parser.add_argument('--profile', default='mock')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    payload = build_manifest(args.profile, config_path=args.config_path)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + '\n', encoding='utf-8')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
