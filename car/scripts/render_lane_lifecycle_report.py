#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.lane_registry import lane_registry_payload



def main() -> int:
    registry = lane_registry_payload(include_experimental=True)
    payload = {
        'status': 'ok',
        'reportScope': 'lane_lifecycle',
        'laneCount': len(registry),
        'mainlineLanes': sorted([key for key, entry in registry.items() if entry['lifecycleStage'] == 'mainline']),
        'experimentalLanes': sorted([key for key, entry in registry.items() if entry['lifecycleStage'] == 'experimental']),
        'rollbackOnlyLanes': sorted([key for key, entry in registry.items() if entry['lifecycleStage'] == 'rollback_only']),
        'defaultVisibleLanes': sorted([key for key, entry in registry.items() if entry['defaultSurfaceExposure'] == 'default_visible']),
        'hiddenByDefaultLanes': sorted([key for key, entry in registry.items() if entry['defaultSurfaceExposure'] == 'hidden_by_default']),
        'lanes': registry,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
