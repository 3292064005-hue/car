#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


from runtime_artifacts import (
    describe_file,
    extend_ros_import_path,
    runtime_artifact_dir,
    runtime_evidence_index_path,
    runtime_metrics_path,
)

extend_ros_import_path()

from robot_monitor.evidence_report import build_evidence_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate evidence summary report from metrics and evidence index.')
    parser.add_argument('--runtime-dir', default=str(runtime_artifact_dir()))
    parser.add_argument('--metrics', default='')
    parser.add_argument('--evidence', default='')
    parser.add_argument('--output', default='-')
    parser.add_argument('--target-environment-acceptance', default='/tmp/target_environment_acceptance.json')
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    metrics_path = Path(args.metrics) if str(args.metrics).strip() else runtime_metrics_path(args.runtime_dir)
    evidence_path = Path(args.evidence) if str(args.evidence).strip() else runtime_evidence_index_path(args.runtime_dir)
    report = build_evidence_report(metrics_path=metrics_path, evidence_index_path=evidence_path, target_environment_acceptance_path=args.target_environment_acceptance)
    report['sourceArtifacts'] = {
        'runtimeDir': str(runtime_artifact_dir(args.runtime_dir)),
        'metrics': describe_file(metrics_path),
        'evidenceIndex': describe_file(evidence_path),
    }
    report['inputCoverage'] = 'complete' if report['sourceArtifacts']['metrics']['exists'] and report['sourceArtifacts']['evidenceIndex']['exists'] else 'missing'
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
