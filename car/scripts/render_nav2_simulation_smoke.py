#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_navigation.navigation_acceptance import write_navigation_acceptance_artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render nav2 simulation smoke acceptance artifact.')
    parser.add_argument('--output', required=True)
    parser.add_argument('--provider-name', default='nav2_provider')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tests = [
        'ros2_ws/src/robot_tests/test_nav2_adapter_node.py',
        'ros2_ws/src/robot_tests/test_navigation_provider_contract.py',
    ]
    completed = subprocess.run([sys.executable, '-m', 'pytest', '-q', *tests], check=False)
    payload = {
        'schemaVersion': 1,
        'artifactType': 'nav2_simulation_smoke',
        'providerName': args.provider_name,
        'passed': completed.returncode == 0,
        'capturedAtUtc': datetime.now(timezone.utc).isoformat(),
        'testsExecuted': tests,
    }
    write_navigation_acceptance_artifact(args.output, payload)
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())
