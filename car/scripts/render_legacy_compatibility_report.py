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

from robot_contracts.legacy_compatibility import LEGACY_COMPATIBILITY_POLICY
from robot_utils.legacy_compat_audit import read_legacy_audit

DEFAULT_AUDIT_PATH = '/tmp/inspection_robot/legacy_compatibility_audit.json'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render the declared legacy compatibility retirement policy and runtime usage audit.')
    parser.add_argument('--audit-path', default=DEFAULT_AUDIT_PATH)
    parser.add_argument('--output', default='-')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit_path = Path(args.audit_path)
    runtime = read_legacy_audit(audit_path)
    motion_hits = int(runtime.get('motionInputAliasHits', 0) or 0)
    ack_hits = int(runtime.get('ackStatusAliasEmissionHits', 0) or 0)
    payload = {
        **LEGACY_COMPATIBILITY_POLICY,
        'auditPath': str(audit_path),
        'runtimeAudit': {
            'artifactPresent': audit_path.is_file(),
            'motionInputAliasHits': motion_hits,
            'ackStatusAliasEmissionHits': ack_hits,
            'recentEvents': list(runtime.get('recentEvents', [])),
        },
        'canAdvanceMilestones': {
            'remove_motion_input_tolerance': motion_hits == 0,
            'remove_ack_status_alias': ack_hits == 0,
        },
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output == '-':
        print(text)
    else:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
