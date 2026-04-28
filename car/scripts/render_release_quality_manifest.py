#!/usr/bin/env python3
from __future__ import annotations

"""Render one release-quality manifest aligned with executable evidence lanes.

The manifest status must not claim a higher readiness level than the executed
verification lanes actually support. Common backend checks alone are therefore
insufficient to mark the system as ready for release. Final delivery remains
blocked until target-environment acceptance reaches the repository's strongest
accepted tier.
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
from runtime_surface_inventory import runtime_signal_matrix_payload

STATUS_EVIDENCE_CLASS = {
    'evidence_incomplete': 'unit_stubbed',
    'ready_backend_only': 'unit_stubbed',
    'ready_frontend_mocked_transport': 'integration_mocked_transport',
    'ready_live_ros_mock_robot': 'integration_live_ros_mock_robot',
    'ready_operator_e2e_mock_robot': 'integration_live_ros_mock_robot',
}

_TARGET_ENVIRONMENT_RELEASE_STATUSES = {
    'target_environment_accepted',
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
    parser.add_argument('--profile', default='mock')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--profile-report-path', default='/tmp/profile_minimal.json')
    parser.add_argument('--evidence-report-path', default='/tmp/evidence_report.json')
    parser.add_argument('--acceptance-report-path', default='/tmp/acceptance_report.json')
    parser.add_argument('--target-environment-acceptance-path', default='/tmp/target_environment_acceptance.json')
    return parser.parse_args()


def _load_json_payload(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _resolve_runtime_contract_context(*, profile: str, config_path: str | None, profile_report_path: str) -> tuple[str, str | None, dict[str, Any]]:
    profile_report = _load_json_payload(profile_report_path)
    effective_profile = str(profile or 'mock').strip() or 'mock'
    effective_config_path = config_path
    reported_profile = profile_report.get('profile')
    if isinstance(reported_profile, dict):
        candidate = str(reported_profile.get('name', '')).strip()
        if candidate:
            effective_profile = candidate
    config_resolution = profile_report.get('config_resolution')
    if effective_config_path is None and isinstance(config_resolution, dict):
        raw_input = str(config_resolution.get('raw_input', '') or '').strip()
        config_root = str(config_resolution.get('config_root', '') or '').strip()
        effective_config_path = raw_input or config_root or None
    return effective_profile, effective_config_path, profile_report if isinstance(profile_report, dict) else {}


def _derive_release_status(*, common_checks_complete: bool, frontend_lane: bool, ros_smoke_lane: bool, integrated_frontend_smoke_lane: bool) -> str:
    if not common_checks_complete:
        return 'evidence_incomplete'
    if integrated_frontend_smoke_lane and ros_smoke_lane and frontend_lane:
        return 'ready_operator_e2e_mock_robot'
    if ros_smoke_lane:
        return 'ready_live_ros_mock_robot'
    if frontend_lane:
        return 'ready_frontend_mocked_transport'
    return 'ready_backend_only'


def _blocking_issue(*, code: str, title: str, lane: str, reason: str) -> dict[str, str]:
    return {'code': code, 'title': title, 'lane': lane, 'reason': reason}


def _gate_state(*, title: str, satisfied: bool, blocking: bool, reason: str, evidence_key: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'title': title,
        'satisfied': bool(satisfied),
        'blocking': bool(blocking),
        'reason': reason,
        'evidenceClass': evidence_class_payload(evidence_key),
        'details': details or {},
    }


def _delivery_evidence_tiers(*, common_checks_complete: bool, frontend_lane: bool, ros_smoke_lane: bool, integrated_frontend_smoke_lane: bool, target_payload: dict[str, Any]) -> dict[str, Any]:
    coverage = target_payload.get('verificationCoverage', {}) if isinstance(target_payload.get('verificationCoverage', {}), dict) else {}
    tiers = {
        'sourcePackageValid': bool(common_checks_complete),
        'hostHarnessValid': bool(common_checks_complete and ros_smoke_lane),
        'operatorE2EMockValid': bool(common_checks_complete and frontend_lane and ros_smoke_lane and integrated_frontend_smoke_lane),
        'targetEnvironmentValid': str(target_payload.get('status', '') or '') == 'target_environment_accepted',
        'realBoardValid': bool(coverage.get('hardwareInLoopVerified', False)),
    }
    highest = 'incomplete'
    if tiers['realBoardValid']:
        highest = 'real-board-valid'
    elif tiers['targetEnvironmentValid']:
        highest = 'target-environment-valid'
    elif tiers['operatorE2EMockValid']:
        highest = 'operator-e2e-mock-valid'
    elif tiers['hostHarnessValid']:
        highest = 'host-harness-valid'
    elif tiers['sourcePackageValid']:
        highest = 'source-package-valid'
    return {**tiers, 'highestTier': highest, 'finalDeliveryEligible': bool(tiers['targetEnvironmentValid'])}


def _build_gate_states(*, common_checks_complete: bool, frontend_lane: bool, ros_smoke_lane: bool, integrated_frontend_smoke_lane: bool, profile: str, config_path: str | None, target_environment_acceptance_path: str) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    runtime_signal_contract = runtime_signal_matrix_payload(profile, config_path=config_path)
    target_payload = _load_json_payload(target_environment_acceptance_path)
    target_status = str(target_payload.get('status', '')).strip()
    target_gate_satisfied = target_status in _TARGET_ENVIRONMENT_RELEASE_STATUSES
    gate_states = {
        'common_checks': _gate_state(
            title='Common checks',
            satisfied=common_checks_complete,
            blocking=True,
            reason='Common checks completed.' if common_checks_complete else 'Common checks are incomplete.',
            evidence_key='unit_stubbed',
        ),
        'frontend_lane': _gate_state(
            title='Frontend lane',
            satisfied=frontend_lane,
            blocking=True,
            reason='Frontend lane executed.' if frontend_lane else 'Frontend lane has not been executed.',
            evidence_key='integration_mocked_transport',
        ),
        'ros_smoke_lane': _gate_state(
            title='ROS smoke lane',
            satisfied=ros_smoke_lane,
            blocking=True,
            reason='ROS smoke lane executed.' if ros_smoke_lane else 'Mock-system ROS smoke lane has not been executed.',
            evidence_key='integration_live_ros_mock_robot',
        ),
        'integrated_frontend_bridge_smoke': _gate_state(
            title='Integrated frontend + web bridge smoke',
            satisfied=integrated_frontend_smoke_lane,
            blocking=True,
            reason='Integrated frontend smoke executed.' if integrated_frontend_smoke_lane else 'Operator path smoke lane has not been executed.',
            evidence_key='integration_live_ros_mock_robot',
        ),
        'runtime_consumer_closure': _gate_state(
            title='Runtime consumer closure',
            satisfied=bool(runtime_signal_contract['runtime_consumer_closure_completed']),
            blocking=True,
            reason='Required runtime signals have runtime consumers.' if runtime_signal_contract['runtime_consumer_closure_completed'] else 'Required runtime signals still have unresolved runtime consumer gaps.',
            evidence_key='integration_live_ros_mock_robot',
            details={
                'profile': runtime_signal_contract['profile'],
                'configPath': config_path,
                'reportScope': runtime_signal_contract['report_scope'],
                'mainlineRuntimeGaps': runtime_signal_contract['mainline_runtime_gaps'],
            },
        ),
        'target_environment_acceptance': _gate_state(
            title='Target environment acceptance',
            satisfied=target_gate_satisfied,
            blocking=True,
            reason='Target environment acceptance reached final-delivery strength.' if target_gate_satisfied else 'Target environment acceptance is missing or below final-delivery strength.',
            evidence_key='hardware_in_loop',
            details={
                'artifactPath': target_environment_acceptance_path,
                'artifactStatus': target_status or None,
                'acceptedStatuses': sorted(_TARGET_ENVIRONMENT_RELEASE_STATUSES),
            },
        ),
    }
    blocking_issues: list[dict[str, str]] = []
    for key, gate in gate_states.items():
        if gate['blocking'] and not gate['satisfied']:
            blocking_issues.append(_blocking_issue(code=key, title=str(gate['title']), lane=key, reason=str(gate['reason'])))
    return gate_states, blocking_issues, runtime_signal_contract, target_payload


def build_quality_manifest(*, common_checks_complete: bool, frontend_lane: bool, ros_smoke_lane: bool, integrated_frontend_smoke_lane: bool, profile: str, config_path: str | None, profile_report_path: str, evidence_report_path: str, acceptance_report_path: str, target_environment_acceptance_path: str) -> dict[str, Any]:
    effective_profile, effective_config_path, profile_report = _resolve_runtime_contract_context(profile=profile, config_path=config_path, profile_report_path=profile_report_path)
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
    status = _derive_release_status(common_checks_complete=common_checks_complete, frontend_lane=frontend_lane, ros_smoke_lane=ros_smoke_lane, integrated_frontend_smoke_lane=integrated_frontend_smoke_lane)
    gate_states, blocking_issues, runtime_signal_contract, target_payload = _build_gate_states(
        common_checks_complete=common_checks_complete,
        frontend_lane=frontend_lane,
        ros_smoke_lane=ros_smoke_lane,
        integrated_frontend_smoke_lane=integrated_frontend_smoke_lane,
        profile=effective_profile,
        config_path=effective_config_path,
        target_environment_acceptance_path=target_environment_acceptance_path,
    )
    hardware_boundary = runtime_signal_contract.get('hardwareBoundary', {}) if isinstance(runtime_signal_contract.get('hardwareBoundary', {}), dict) else {}
    embedded_runtime_layout = hardware_boundary.get('embeddedRuntimeLayout', {}) if isinstance(hardware_boundary.get('embeddedRuntimeLayout', {}), dict) else {}
    release_gate_satisfied = len(blocking_issues) == 0
    delivery_tiers = _delivery_evidence_tiers(
        common_checks_complete=common_checks_complete,
        frontend_lane=frontend_lane,
        ros_smoke_lane=ros_smoke_lane,
        integrated_frontend_smoke_lane=integrated_frontend_smoke_lane,
        target_payload=target_payload,
    )
    release_decision = 'target_environment_release_candidate' if release_gate_satisfied else 'blocked'
    readiness_evidence_key = STATUS_EVIDENCE_CLASS[status]
    target_coverage = target_payload.get('verificationCoverage', {}) if isinstance(target_payload.get('verificationCoverage', {}), dict) else {}
    return {
        'schemaVersion': 4,
        'generatedAtUtc': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'releaseReadinessLevel': status,
        'releaseGateSatisfied': release_gate_satisfied,
        'releaseDecision': release_decision,
        'releaseRuntimeContext': {
            'profile': effective_profile,
            'configPath': effective_config_path,
            'profileReportConsumed': bool(profile_report),
        },
        'deliveryEvidenceTiers': delivery_tiers,
        'blockingIssues': blocking_issues,
        'gateStates': gate_states,
        'releaseGateManifest': manifest_payload(),
        'runtimePolicy': runtime_policy_snapshot(),
        'runtimeSignalContract': {
            'profile': runtime_signal_contract['profile'],
            'reportScope': runtime_signal_contract['report_scope'],
            'runtimeConsumerClosureCompleted': runtime_signal_contract['runtime_consumer_closure_completed'],
            'mainlineRuntimeGaps': runtime_signal_contract['mainline_runtime_gaps'],
            'topicPruningApplied': runtime_signal_contract['topic_pruning_applied'],
            'hardwareBoundary': hardware_boundary,
            'embeddedRuntimeLayout': embedded_runtime_layout,
        },
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
                'releaseDecision additionally requires runtime consumer closure and target-environment acceptance at final-delivery strength',
            ],
        },
        'verificationScope': {
            'surface': 'host_harness_mock_robot_until_target_environment_is_verified',
            'operatorPathVerified': integrated_frontend_smoke_lane,
            'realHardwareVerified': bool(delivery_tiers['realBoardValid']),
            'hardwareInLoopVerified': bool(delivery_tiers['realBoardValid']),
            'realBoardObserved': bool(target_coverage.get('realBoardObserved', False)),
            'targetEnvironmentAcceptanceRequiredForRelease': True,
            'hardwareInLoopRequiredForRealBoardClaims': True,
            'hardwareBoundary': hardware_boundary,
            'embeddedRuntimeLayout': embedded_runtime_layout,
            'verificationTiers': {
                'highestVerifiedEvidenceClass': evidence_class_payload(strongest),
                'targetEnvironmentFloor': evidence_class_payload('hardware_in_loop'),
                'realBoardClaimFloor': evidence_class_payload('hardware_in_loop'),
            },
            'claimBoundaryNotes': [
                'this manifest covers repository/common/frontend/mock-robot lanes plus the supplied target-environment artifact',
                'final-delivery release claims stay blocked until target_environment_accepted is present',
                'hardwareBoundary and embeddedRuntimeLayout snapshots are sourced from the same runtime signal contract consumed by launch/profile reports',
            ],
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
        profile=args.profile,
        config_path=args.config_path,
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
