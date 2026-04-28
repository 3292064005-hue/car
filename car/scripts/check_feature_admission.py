#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.feature_admission import feature_admission_payload, validate_feature_admission_registry



def main() -> int:
    payload = {
        'status': 'ok',
        'featureCount': len(feature_admission_payload()),
        'validationErrors': validate_feature_admission_registry(),
    }
    if payload['validationErrors']:
        payload['status'] = 'error'
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
