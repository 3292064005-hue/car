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

from robot_monitor.evidence_report import build_evidence_report  # noqa: E402


def _default_metrics_path() -> Path:
    return ROOT / 'tmp' / 'inspection_robot' / 'metrics.json'


def _default_evidence_index_path() -> Path:
    return ROOT / 'tmp' / 'inspection_robot' / 'evidence_index.json'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate evidence summary report from metrics and evidence index.')
    parser.add_argument('--metrics', default=str(_default_metrics_path()))
    parser.add_argument('--evidence', default=str(_default_evidence_index_path()))
    parser.add_argument('--output', default='-')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_evidence_report(metrics_path=args.metrics, evidence_index_path=args.evidence)
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output == '-':
        print(payload)
    else:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
