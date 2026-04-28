#!/usr/bin/env python3
from __future__ import annotations

"""Validate command handler semantic alignment against ROS interfaces."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.command_interface_manifest import command_interface_manifest_payload, validate_command_interface_manifest


def main() -> int:
    errors = validate_command_interface_manifest(repo_root=ROOT)
    payload = {
        'status': 'ok' if not errors else 'error',
        'commandCount': len(command_interface_manifest_payload()),
        'validationErrors': errors,
        'manifest': command_interface_manifest_payload(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
