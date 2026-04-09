#!/usr/bin/env python3
"""Render structured host-harness acceptance evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from typing import Any

from runtime_artifacts import describe_file, extend_ros_import_path

extend_ros_import_path()

from robot_utils.acceptance_bundle import ACCEPTANCE_SCHEMA_VERSION, build_verification_identity
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
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--profile-name', default='target_acceptance')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    acceptance = _load_json(args.acceptance_report)
    manifest = _load_json(args.quality_manifest)
    acceptance_gate = str(acceptance.get('acceptanceGate', '') or '')
    manifest_status = str(manifest.get('status', '') or '')
    passed = acceptance_gate == 'pass' and manifest_status in {'ready_operator_e2e_mock_robot', 'ready_live_ros_mock_robot', 'ready_operator_e2e', 'ready'}
    payload = {
        'schemaVersion': ACCEPTANCE_SCHEMA_VERSION,
        'artifactType': 'host_harness_acceptance',
        'capturedAtUtc': datetime.now(timezone.utc).isoformat(),
        'sourceArtifacts': {
            'acceptanceReport': describe_file(args.acceptance_report),
            'releaseQualityManifest': describe_file(args.quality_manifest),
        },
        'verificationIdentity': build_verification_identity(
            repo_root=Path(__file__).resolve().parents[1],
            config_path=args.config_path,
            profile_name=args.profile_name,
            hardware_identity={},
            firmware_identity={},
        ),
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
