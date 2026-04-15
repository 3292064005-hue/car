from __future__ import annotations

from pathlib import Path
from typing import Any

from robot_utils.acceptance_bundle import validate_target_environment_acceptance
from robot_utils.config_loader import load_structured_file
from robot_utils.verification_evidence import evidence_class_payload, strongest_evidence_class


def load_json(path: str | Path) -> dict[str, Any]:
    payload = load_structured_file(str(path), {})
    return payload if isinstance(payload, dict) else {}




def _target_acceptance_payload(path: str | Path | None) -> tuple[dict[str, Any], bool]:
    if not path:
        return {}, False
    payload = load_json(path)
    return payload, bool(Path(path).is_file())


def _target_acceptance_verified(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    validation = validate_target_environment_acceptance(
        payload,
        repo_root=Path(__file__).resolve().parents[4],
        config_path=None,
    )
    return validation.valid


def build_evidence_report(*, metrics_path: str | Path, evidence_index_path: str | Path, target_environment_acceptance_path: str | Path | None = None) -> dict[str, Any]:
    metrics = load_json(metrics_path)
    evidence = load_json(evidence_index_path)
    metrics_exists = Path(metrics_path).is_file()
    evidence_exists = Path(evidence_index_path).is_file()
    input_coverage = 'complete' if metrics_exists and evidence_exists else 'missing'
    highest_local_key = 'integration_live_ros_mock_robot' if input_coverage == 'complete' else 'unit_stubbed'
    target_acceptance, target_present = _target_acceptance_payload(target_environment_acceptance_path)
    target_claim_boundary = target_acceptance.get('verificationCoverage', {}).get('claimBoundary', {}) if isinstance(target_acceptance.get('verificationCoverage', {}), dict) else {}
    target_highest_key = str(target_claim_boundary.get('highestObservedEvidenceClass', {}).get('key', '') or '') if isinstance(target_claim_boundary, dict) else ''
    highest_observed_key = strongest_evidence_class([highest_local_key, target_highest_key])
    highest_local_evidence = evidence_class_payload(highest_local_key)
    highest_observed_evidence = evidence_class_payload(highest_observed_key)
    target_verified = _target_acceptance_verified(target_acceptance)
    report = {
        'metrics_path': str(metrics_path),
        'evidence_index_path': str(evidence_index_path),
        'health': evidence.get('health', 'unknown'),
        'readiness': evidence.get('readiness', 'unknown'),
        'last_fault': evidence.get('last_fault', ''),
        'last_safe_stop': evidence.get('last_safe_stop', ''),
        'last_recovery': evidence.get('last_recovery', ''),
        'last_qrcode': evidence.get('last_qrcode', ''),
        'last_protocol_issue': evidence.get('last_protocol_issue', ''),
        'last_snapshot': evidence.get('last_snapshot', ''),
        'snapshot_count': len(evidence.get('recent_snapshots', [])),
        'recent_event_count': len(evidence.get('recent_events', [])),
        'recent_events': evidence.get('recent_events', []),
        'recent_snapshots': evidence.get('recent_snapshots', []),
        'command_audit_summary': evidence.get('command_audit_summary', []),
        'reconnect_count': metrics.get('reconnect_count', 0),
        'protocol_errors': metrics.get('protocol_errors', 0),
        'events_logged': metrics.get('events_logged', 0),
        'summaries_published': metrics.get('summaries_published', 0),
        'health_transitions': metrics.get('health_transitions', 0),
        'voice_reject_count': metrics.get('voice_reject_count', 0),
        'safe_stop_count': metrics.get('safe_stop_count', 0),
        'verificationScope': {
            'source': 'runtime_artifacts_only',
            'inputCoverage': input_coverage,
            'highestObservedEvidenceClass': highest_observed_evidence,
            'highestLocalEvidenceClass': highest_local_evidence,
            'targetEnvironmentAcceptanceRequired': True,
            'targetEnvironmentAcceptancePresent': target_present,
            'targetEnvironmentAcceptanceVerified': target_verified,
            'hardwareInLoopRequiredForRealBoardClaims': True,
            'supportedClaims': list(highest_observed_evidence['supportedClaims']),
            'claimBoundaryNotes': [
                'runtime metrics/evidence index artifacts support repository and host-runtime review only',
                'target-environment acceptance must be captured separately before final delivery claims are made',
                'target acceptance is only verified when live ROS runtime, host harness, observational probe, and hardware-in-loop evidence all agree',
                'hardware-in-loop evidence is still required for any direct real-board behavior claim',
            ],
        },
    }
    report['status'] = 'ready_for_review' if report['health'] in {'good', 'degraded'} and input_coverage == 'complete' else 'needs_attention'
    report['reviewGate'] = 'host_runtime_review_ready' if report['status'] == 'ready_for_review' else 'needs_attention'
    blockers = []
    if input_coverage != 'complete':
        blockers.append('runtime_artifacts_incomplete')
    if report['status'] != 'ready_for_review':
        blockers.append('host_runtime_review_not_ready')
    if not target_present:
        blockers.append('target_environment_acceptance_artifact_missing')
    if target_present and not target_verified:
        blockers.append('target_environment_acceptance_not_verified')
    if not target_verified:
        blockers.append('hardware_in_loop_evidence_missing')
    report['finalDeliveryBlockers'] = blockers
    report['finalDeliveryEligible'] = len(blockers) == 0
    return report
