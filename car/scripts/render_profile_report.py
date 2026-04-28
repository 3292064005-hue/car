#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from robot_bringup.config_resolution import resolve_bringup_config
from robot_contracts.lane_registry import lane_registry_payload
from robot_contracts.signal_ownership import governance_signal_registry_payload
from robot_bringup.dependency_matrix import dependency_plan_for
from robot_bringup.launch_profiles import get_launch_profile, supported_profiles
from robot_bringup.matrix_contracts import load_bringup_matrices, profile_feature_matrix, surface_contract_for_profile
from robot_bringup.preflight import build_preflight_report
from robot_bridge.runtime_factory import runtime_policy_snapshot
from robot_navigation.provider_contract import navigation_provider_activation
from robot_navigation.navigation_acceptance import resolve_nav2_acceptance_artifact_paths
from runtime_surface_inventory import load_hardware_boundary_snapshot





def _load_navigation_provider_contract(config_dir: Path) -> dict[str, object]:
    source = config_dir / 'navigation.yaml'
    if not source.is_file():
        return navigation_provider_activation('simple_nav_provider')
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    config = payload.get('robot_navigation', payload) if isinstance(payload, dict) else {}
    ros_params = config.get('ros__parameters', {}) if isinstance(config, dict) and isinstance(config.get('ros__parameters', {}), dict) else {}
    provider_name = str(ros_params.get('provider_name', 'simple_nav_provider') or 'simple_nav_provider').strip() or 'simple_nav_provider'
    allow_experimental = str(os.environ.get('ROBOT_ALLOW_EXPERIMENTAL_NAVIGATION_PROVIDER', '0') or '0').strip() == '1'
    acceptance_artifact_paths = resolve_nav2_acceptance_artifact_paths(
        ros_params,
        config_root=config_dir,
        runtime_dir=os.environ.get('INSPECTION_ROBOT_RUNTIME_DIR', '/tmp/inspection_robot'),
    )
    return navigation_provider_activation(
        provider_name,
        allow_experimental=allow_experimental,
        acceptance_artifact_paths=acceptance_artifact_paths,
        reference_config_path=str(config_dir),
    )

def build_report(profile_name: str, *, config_path: str | None = None) -> dict[str, object]:
    profile = get_launch_profile(profile_name, config_path=config_path)
    resolved = resolve_bringup_config(config_path)
    config_dir = resolved.config_root
    matrices = load_bringup_matrices(config_path)
    capability_snapshot = profile_feature_matrix(profile, config_path=config_path)
    navigation_provider = _load_navigation_provider_contract(config_dir)
    hardware_boundary = load_hardware_boundary_snapshot(config_dir)
    return {
        'profile': profile.to_dict(),
        'supported_profiles': list(supported_profiles(config_path=config_path)),
        'config_dir': str(config_dir),
        'config_files': sorted(path.name for path in config_dir.glob('*.yaml')),
        'required_configs': ['bridge.yaml', 'control.yaml', 'decision.yaml', 'monitor.yaml', 'vision.yaml', 'voice.yaml', 'fault.yaml'],
        'config_resolution': {
            'config_root': str(resolved.config_root),
            'launch_profiles_path': str(resolved.launch_profiles_path),
            'raw_input': resolved.raw_input,
            'source': resolved.source,
        },
        'dependency_plan': dependency_plan_for(profile, surface='backend').to_dict(),
        'runtime_policy': runtime_policy_snapshot(),
        'bringup_matrices': matrices.to_dict(),
        'surface_contract': surface_contract_for_profile(profile, config_path=config_path),
        'capability_snapshot': capability_snapshot,
        'lane_registry': lane_registry_payload(include_experimental=True),
        'signal_ownership_registry': governance_signal_registry_payload(),
        'navigation_provider': navigation_provider,
        'hardware_boundary': {
            **hardware_boundary,
            'launch_profile_requires_real_robot': not profile.use_mock_robot,
            'board_validation_scope': 'repo_root_launch_and_dependency_checks_only',
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
