#!/usr/bin/env python3
from __future__ import annotations

import json


def main() -> int:
    payload = {
        'status': 'ok',
        'reportScope': 'system_replay_evidence',
        'frontendReplay': {
            'kind': 'browser_local_json_demo',
            'bundleKind': 'offline-session-export',
            'countsAsSystemEvidence': False,
            'notes': ['Frontend local replay remains a UX/debug helper only.'],
        },
        'systemReplay': {
            'kind': 'system-replay-bundle',
            'countsAsSystemEvidence': True,
            'supportedFormats': ['rosbag2', 'mcap', 'system-replay-bundle-json'],
            'requiredBundleMembers': ['topics', 'serviceActionEvents', 'sessionMetadata', 'traceCorrelation'],
            'minimumUseCases': ['acceptance_review', 'fault_reproduction', 'release_audit'],
            'runtimeProducer': 'robot_monitor',
            'runtimeBundlePath': '/tmp/inspection_robot/system_replay_bundle.json',
            'builderScript': 'scripts/build_system_replay_bundle.py',
            'builderRole': 'offline_repack_or_backfill',
            'schemaVersion': '1.0.0',
        },
        'nonClaims': ['frontend_local_replay_is_not_target_environment_acceptance'],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
