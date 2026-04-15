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

from robot_bridge.runtime_factory import runtime_policy_snapshot
from runtime_surface_inventory import closure_tracks_payload, launch_surface_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render bridge runtime topology policy report')
    parser.add_argument('--output', default='-')
    return parser.parse_args()


def main() -> int:
    policy = runtime_policy_snapshot()
    launch_surface = launch_surface_snapshot()
    payload = {
        'status': 'ok',
        'report_scope': 'policy_artifact_only',
        'closureTracks': closure_tracks_payload(declared_complete=True, observed_complete=False),
        'runtime_launch_surface_changed': bool(launch_surface['operatorBarrierEnabled']),
        'legacy_runtime_removed_from_launch': bool(launch_surface.get('legacyRuntimeRemovedFromDefaultLaunchSurface', False)),
        'policy': policy,
        'launchSurface': launch_surface,
        'mainline_runtime': policy['preferred_runtime'],
        'rollback_runtime': policy['rollback_runtime'],
        'legacy_constraints': [
            'legacy runtime remains rollback-only and should not receive new feature work',
            'release verification should treat legacy runtime as compatibility smoke rather than the default feature lane',
            'default launch surfaces expose split runtime only; legacy monolith is reachable through the explicit rollback gate',
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    args = parse_args()
    if args.output == '-':
        print(text)
    else:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
