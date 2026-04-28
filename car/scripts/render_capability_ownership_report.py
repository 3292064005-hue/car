#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.feature_admission import feature_admission_payload
from robot_contracts.signal_ownership import governance_signal_registry_payload



def main() -> int:
    features = feature_admission_payload()
    signals = governance_signal_registry_payload()
    command_owners = {}
    for feature_id, entry in features.items():
        for command in entry.get('commands', []):
            command_owners[str(command)] = feature_id
    payload = {
        'status': 'ok',
        'reportScope': 'capability_ownership',
        'featureOwners': {key: value['authoritativeNodes'] for key, value in features.items()},
        'commandOwners': command_owners,
        'machineGateReports': sorted([name for name, entry in signals['reports'].items() if entry['evidenceLayer'] == 'machine_gate']),
        'humanSummaryReports': sorted([name for name, entry in signals['reports'].items() if entry['evidenceLayer'] == 'human_summary']),
        'signalRegistry': signals,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
