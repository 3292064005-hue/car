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

from runtime_surface_inventory import load_hardware_boundary_snapshot, resolve_config_root


def build_payload(config_path: str | None = None) -> dict[str, object]:
    config_root = resolve_config_root(config_path)
    hardware_boundary = load_hardware_boundary_snapshot(config_root)
    return {
        'status': 'ok',
        'repositoryRole': 'ubuntu_authoritative_runtime_plus_board_boundary_contract' ,
        'authoritativeWriteEntry': 'robot_api_server:9100/ws',
        'observerSurface': 'robot_web_bridge:9001/ws',
        'repositoryClaims': {
            'ubuntuRuntimeClosure': True,
            'boardRuntimeInRepo': False,
            'targetEnvironmentAcceptanceInRepo': False,
        },
        'closureStopPoints': {
            'browser_to_ubuntu': 'closed_in_repo',
            'bridge_to_board_runtime': 'soft_driver_boundary_only_until_verified_board_driver_acceptance',
        },
        'authorityChain': [
            'browser_frontend',
            'robot_api_server',
            'robot_web_bridge',
            'robot_decision_or_robot_control',
            'robot_bridge',
            'robot_direct_driver',
            'board_boundary_contract_or_verified_board_runtime',
        ],
        'hardwareBoundary': hardware_boundary,
        'governanceDocs': [
            'docs/governance/repository-boundaries.md',
            'docs/governance/feature-admission.md',
            'docs/governance/capability-ownership.md',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Render repository boundary governance report.')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    payload = build_payload(args.config_path)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + '\n', encoding='utf-8')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
