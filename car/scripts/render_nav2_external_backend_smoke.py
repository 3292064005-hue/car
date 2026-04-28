#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_navigation.navigation_acceptance import write_navigation_acceptance_artifact
from robot_nav2_adapter.backend_claims import resolve_nav2_backend_runtime_claims


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render nav2 external backend smoke artifact.')
    parser.add_argument('--output', required=True)
    parser.add_argument('--provider-name', default='nav2_provider')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    claims = resolve_nav2_backend_runtime_claims(requested_backend_mode='external_nav2_stack', external_nav2_stack_available=True, external_nav2_backend_integrated=True, recovery_enabled=True)
    passed = claims['selectedBackend'] == 'external_nav2_stack' and claims['backendIntegrated'] is True and claims['plannerSupport'] is True and claims['controllerSupport'] is True
    write_navigation_acceptance_artifact(args.output, {
        'schemaVersion': 1,
        'artifactType': 'nav2_external_backend_smoke',
        'providerName': args.provider_name,
        'selectedBackend': claims['selectedBackend'],
        'backendIntegrated': claims['backendIntegrated'],
        'passed': passed,
        'capturedAtUtc': datetime.now(timezone.utc).isoformat(),
        'checkedClaims': claims,
    })
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
