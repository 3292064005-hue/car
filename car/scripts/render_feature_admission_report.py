#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.feature_admission import feature_admission_payload, validate_feature_admission_registry


def main() -> int:
    parser = argparse.ArgumentParser(description='Render feature admission governance report.')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    registry = feature_admission_payload()
    payload = {
        'status': 'ok' if not validate_feature_admission_registry() else 'error',
        'reportScope': 'feature_admission_governance',
        'featureCount': len(registry),
        'features': registry,
        'validationErrors': validate_feature_admission_registry(),
        'notes': [
            'Each user-visible feature must declare authority, config, tests, acceptance artifacts, and rollback paths.',
            'Board-dependent features advertise target_environment_acceptance as a stronger artifact class.',
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + '\n', encoding='utf-8')
    else:
        print(text)
    return 0 if payload['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
