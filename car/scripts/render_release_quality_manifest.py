#!/usr/bin/env python3
from __future__ import annotations

"""Render one release-quality manifest aligned with executable evidence lanes.

The manifest status must not claim a higher readiness level than the executed
verification lanes actually support. Common backend checks alone are therefore
insufficient to mark the system as ready for release.
"""

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

from release_gate_manifest import LANES, manifest_payload
from robot_bridge.runtime_factory import runtime_policy_snapshot
from robot_utils.verification_evidence import evidence_class_payload, strongest_evidence_class

STATUS_EVIDENCE_CLASS = {
    'evidence_incomplete': 'unit_stubbed',
    'ready_backend_only': 'unit_stubbed',
    'ready_frontend_mocked_transport': 'integration_mocked_transport',
    'ready_live_ros_mock_robot': 'integration_live_ros_mock_robot',
    'ready_operator_e2e_mock_robot': 'integration_live_ros_mock_robot',
}



def _parse_bool(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise argparse.ArgumentTypeError(f'invalid boolean value: {value!r}')



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render release quality manifest.')
    parser.add_argument('--output', default='/tmp/release_quality_manifest.json')
    parser.add_argument('--common-checks-complete', type=_parse_bool, default=False)
    parser.add_argument('--frontend-lane', type=_parse_bool, default=False)
    parser.add_argument('--ros-smoke-lane', type=_parse_bool, default=False)
    parser.add_argument('--integrated-frontend-smoke-lane', type=_parse_bool, default=False)
    parser.add_argument('--history-dir', default='')
    parser.add_argument('--profile-report-path', default='/tmp/profile_minimal.json')
    parser.add_argument('--evidence-report-path', default='/tmp/evidence_report.json')
    parser.add_argument('--acceptance-report-path', default='/tmp/acceptance_report.json')
    parser.add_argument('--target-environment-acceptance-path', default='/tmp/target_environment_acceptance.json')
    return parser.parse_args()



def _derive_release_status(
    *,
    common_checks_complete: bool,
    frontend_lane: bool,
    ros_smoke_lane: bool,
    integrated_frontend_smoke_lane: bool,
) -> str:
    if not common_checks_complete:
        return 'evidence_incomplete'
    if integrated_frontend_smoke_lane and ros_smoke_lane and frontend_lane:
        return 'ready_operator_e2e_mock_robot'
    if ros_smoke_lane:
        return 'ready_live_ros_mock_robot'
    if frontend_lane:
        return 'ready_frontend_mocked_transport'
    return 'ready_backend_only'



def build_quality_manifest(
    *,
    common_checks_complete: bool,
    frontend_lane: bool,
    ros_smoke_lane: bool,
    integrated_frontend_smoke_lane: bool,
    profile_report_path: str,
    evidence_report_path: str,
    acceptance_report_path: str,
    target_environment_acceptance_path: str,
) -> dict[str, Any]:
    coverage = {
        'contractCompatibility': common_checks_complete,
        'configConsistency': common_checks_complete,
        'backendHealth': common_checks_complete,
        'frontendHealth': frontend_lane,
        'bridgeIntegration': ros_smoke_lane,
        'operatorPathEndToEnd': integrated_frontend_smoke_lane,
    }
    lane_execution = {
        'frontend': frontend_lane,
        'ros_smoke': ros_smoke_lane,
        'integrated_frontend_bridge_smoke': integrated_frontend_smoke_lane,
    }
    executed_evidence_classes = ['unit_stubbed']
    if frontend_lane:
        executed_evidence_classes.append('integration_mocked_transport')
    if ros_smoke_lane:
        executed_evidence_classes.append('integration_live_ros_mock_robot')
    strongest = strongest_evidence_class(executed_evidence_classes)
    status = _derive_release_status(
        common_checks_complete=common_checks_complete,
        frontend_lane=frontend_lane,
        ros_smoke_lane=ros_smoke_lane,
        integrated_frontend_smoke_lane=integrated_frontend_smoke_lane,
    )
    readiness_evidence_key = STATUS_EVIDENCE_CLASS[status]
    return {
        'schemaVersion': 2,
        'generatedAtUtc': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'legacyStatus': 'ready_for_release' if status == 'ready_operator_e2e_mock_robot' else 'evidence_incomplete',
        'releaseReadinessLevel': status,
        'releaseGateManifest': manifest_payload(),
        'runtimePolicy': runtime_policy_snapshot(),
        'qualityScorecard': coverage,
        'executedLanes': lane_execution,
        'riskSurfaces': {lane.key: lane.risk_surface for lane in LANES},
        'artifacts': {
            'profileReport': describe_file(profile_report_path),
            'evidenceReport': describe_file(evidence_report_path),
            'acceptanceReport': describe_file(acceptance_report_path),
            'targetEnvironmentAcceptance': describe_file(target_environment_acceptance_path),
        },
        'evidenceSummary': {
            'executedEvidenceClasses': [evidence_class_payload(key) for key in executed_evidence_classes],
            'highestVerifiedEvidenceClass': evidence_class_payload(strongest),
            'statusEvidenceFloor': evidence_class_payload(readiness_evidence_key),
            'claimBoundary': list(evidence_class_payload(strongest)['supportedClaims']),
            'notes': [
                'release-quality evidence does not imply real-board verification unless hardware-in-loop evidence is present',
                'operator-facing claims must not exceed highestVerifiedEvidenceClass.supportedClaims',
                'status is derived from executed lanes and cannot be promoted by backend/common checks alone',
            ],
        },
        'verificationScope': {
            'surface': 'host_harness_mock_robot_only',
            'operatorPathVerified': integrated_frontend_smoke_lane,
            'realHardwareVerified': False,
            'hardwareInLoopVerified': False,
            'realBoardObserved': False,
            'targetEnvironmentAcceptanceRequiredForRelease': True,
            'hardwareInLoopRequiredForRealBoardClaims': True,
            'verificationTiers': {
                'highestVerifiedEvidenceClass': evidence_class_payload(strongest),
                'targetEnvironmentFloor': evidence_class_payload('integration_live_ros_mock_robot'),
                'realBoardClaimFloor': evidence_class_payload('hardware_in_loop'),
            },
            'claimBoundaryNotes': [
                'this manifest covers repository/common/frontend/mock-robot lanes only',
                'real-board observational probes are captured by target-environment acceptance artifacts, not by release-quality status alone',
            ],
            'deprecatedLegacyAlias': 'ready_for_release' if status == 'ready_operator_e2e_mock_robot' else None,
        },
    }



def write_quality_history(payload: dict[str, Any], *, history_dir: str) -> dict[str, Any] | None:
    if not history_dir:
        return None
    target_dir = Path(history_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = target_dir / f'release_quality_{stamp}.json'
    latest = target_dir / 'latest.json'
    index_path = target_dir / 'index.json'
    entries = sorted([path.name for path in target_dir.glob('release_quality_*.json')] + [target.name])
    history = {'historyDir': str(target_dir), 'latest': str(latest), 'entries': entries}
    payload_with_history = dict(payload)
    payload_with_history['history'] = history
    serialized = json.dumps(payload_with_history, ensure_ascii=False, indent=2)
    target.write_text(serialized, encoding='utf-8')
    latest.write_text(serialized, encoding='utf-8')
    index_path.write_text(json.dumps({'latest': str(latest), 'entries': entries}, ensure_ascii=False, indent=2), encoding='utf-8')
    return history



def main() -> int:
    args = parse_args()
    payload = build_quality_manifest(
        common_checks_complete=args.common_checks_complete,
        frontend_lane=args.frontend_lane,
        ros_smoke_lane=args.ros_smoke_lane,
        integrated_frontend_smoke_lane=args.integrated_frontend_smoke_lane,
        profile_report_path=args.profile_report_path,
        evidence_report_path=args.evidence_report_path,
        acceptance_report_path=args.acceptance_report_path,
        target_environment_acceptance_path=args.target_environment_acceptance_path,
    )
    if args.history_dir:
        history = write_quality_history(payload, history_dir=args.history_dir)
        if history is not None:
            payload['history'] = history
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
