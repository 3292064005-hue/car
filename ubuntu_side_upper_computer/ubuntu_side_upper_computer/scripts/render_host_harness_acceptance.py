#!/usr/bin/env python3
"""Render structured host-harness acceptance evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_utils.verification_evidence import evidence_class_payload


def _load_json(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Render host-harness acceptance evidence.')
    parser.add_argument('--output', default='/tmp/host_harness_acceptance.json')
    parser.add_argument('--acceptance-report', default='/tmp/acceptance_report.json')
    parser.add_argument('--quality-manifest', default='/tmp/release_quality_manifest.json')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    acceptance = _load_json(args.acceptance_report)
    manifest = _load_json(args.quality_manifest)
    acceptance_gate = str(acceptance.get('acceptanceGate', '') or '')
    manifest_status = str(manifest.get('status', '') or '')
    passed = acceptance_gate == 'pass' and manifest_status in {'ready_for_release', 'ready_live_ros_mock_robot', 'ready_operator_e2e', 'ready'}
    payload = {
        'capturedAtUtc': datetime.now(timezone.utc).isoformat(),
        'sourceArtifacts': {
            'acceptanceReport': args.acceptance_report,
            'releaseQualityManifest': args.quality_manifest,
        },
        'acceptanceGate': acceptance_gate or None,
        'qualityManifestStatus': manifest_status or None,
        'evidenceClass': evidence_class_payload('integration_live_ros_mock_robot'),
        'claimBoundary': list(evidence_class_payload('integration_live_ros_mock_robot')['supportedClaims']),
        'passed': passed,
        'status': 'host_harness_passed' if passed else 'host_harness_needs_attention',
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
