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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from release_gate_manifest import LANES, manifest_payload
from robot_bridge.runtime_factory import runtime_policy_snapshot
from robot_utils.verification_evidence import evidence_class_payload, strongest_evidence_class

STATUS_EVIDENCE_CLASS = {
    'evidence_incomplete': 'unit_stubbed',
    'ready_backend_only': 'unit_stubbed',
    'ready_frontend_mocked_transport': 'integration_mocked_transport',
    'ready_live_ros_mock_robot': 'integration_live_ros_mock_robot',
    'ready_for_release': 'integration_live_ros_mock_robot',
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
    return parser.parse_args()


def _derive_release_status(
    *,
    common_checks_complete: bool,
    frontend_lane: bool,
    ros_smoke_lane: bool,
    integrated_frontend_smoke_lane: bool,
) -> str:
    """Derive one readiness status from the executed verification lanes.

    Args:
        common_checks_complete: Whether contract/config/backend checks passed.
        frontend_lane: Whether the isolated frontend lane executed successfully.
        ros_smoke_lane: Whether live ROS + mock robot smoke executed successfully.
        integrated_frontend_smoke_lane: Whether the integrated operator path lane
            executed successfully.

    Returns:
        Stable manifest status label.

    Raises:
        None.

    Boundary behavior:
        Integrated frontend smoke cannot elevate readiness beyond the live ROS
        smoke lane. If integrated smoke is reported without live ROS smoke, the
        status is clamped to the strongest valid lower tier.
    """
    if not common_checks_complete:
        return 'evidence_incomplete'
    if integrated_frontend_smoke_lane and ros_smoke_lane and frontend_lane:
        return 'ready_for_release'
    if ros_smoke_lane:
        return 'ready_live_ros_mock_robot'
    if frontend_lane:
        return 'ready_frontend_mocked_transport'
    return 'ready_backend_only'


def build_quality_manifest(*, common_checks_complete: bool, frontend_lane: bool, ros_smoke_lane: bool, integrated_frontend_smoke_lane: bool) -> dict[str, Any]:
    """Build one release-quality manifest payload.

    Args:
        common_checks_complete: Whether contract/config/backend checks passed.
        frontend_lane: Whether frontend verification succeeded.
        ros_smoke_lane: Whether live ROS smoke succeeded.
        integrated_frontend_smoke_lane: Whether integrated operator E2E smoke succeeded.

    Returns:
        JSON-serializable manifest payload.

    Raises:
        None.
    """
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
        'legacyStatus': 'ready_for_release' if status == 'ready_for_release' else 'evidence_incomplete',
        'releaseReadinessLevel': status,
        'releaseGateManifest': manifest_payload(),
        'runtimePolicy': runtime_policy_snapshot(),
        'qualityScorecard': coverage,
        'executedLanes': lane_execution,
        'riskSurfaces': {lane.key: lane.risk_surface for lane in LANES},
        'artifacts': {
            'profileReport': '/tmp/profile_minimal.json',
            'evidenceReport': '/tmp/evidence_report.json',
            'acceptanceReport': '/tmp/acceptance_report.json',
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
    }


def write_quality_history(payload: dict[str, Any], *, history_dir: str) -> dict[str, Any] | None:
    """Persist one manifest snapshot into the history directory.

    Args:
        payload: Manifest payload to persist.
        history_dir: Target history directory. Empty disables history output.

    Returns:
        History summary payload when enabled; otherwise ``None``.

    Raises:
        None.
    """
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
