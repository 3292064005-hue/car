#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_bringup.environment_checks import build_environment_report



def main() -> int:
    report = build_environment_report(ROOT)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('ok', False) else 1


if __name__ == '__main__':
    raise SystemExit(main())
