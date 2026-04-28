#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_navigation.provider_contract import _provider_package_available, navigation_provider_activation, resolve_navigation_provider
from robot_navigation.navigation_acceptance import write_navigation_acceptance_artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render nav2 provider-switch smoke artifact.')
    parser.add_argument('--output', required=True)
    parser.add_argument('--provider-name', default='nav2_provider')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provider = resolve_navigation_provider(args.provider_name)
    activation = navigation_provider_activation(args.provider_name, allow_experimental=False)
    passed = provider.implemented and _provider_package_available(provider) and activation['activationDecision'] == 'reject' and activation['selectedRuntimeProvider'] == 'simple_nav_provider'
    write_navigation_acceptance_artifact(args.output, {
        'schemaVersion': 1,
        'artifactType': 'nav2_provider_switch_smoke',
        'providerName': args.provider_name,
        'passed': passed,
        'capturedAtUtc': datetime.now(timezone.utc).isoformat(),
        'switchSequence': [args.provider_name, 'simple_nav_provider'],
    })
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
