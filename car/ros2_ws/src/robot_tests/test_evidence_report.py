import json
from pathlib import Path

import pytest

from robot_monitor.evidence_report import build_evidence_report


def _verified_target_payload(verification_identity: dict) -> dict:
    return {
        'schemaVersion': 2,
        'artifactType': 'target_environment_acceptance',
        'status': 'target_environment_accepted',
        'runtime': {'ros2': {'available': True}, 'rclpyAvailable': True},
        'verificationIdentity': verification_identity,
        'evidenceClass': {'key': 'hardware_in_loop'},
        'passed': True,
        'verificationCoverage': {
            'hostHarnessVerified': True,
            'realBoardObserved': True,
            'hardwareInLoopVerified': True,
            'claimBoundary': {'highestObservedEvidenceClass': {'key': 'hardware_in_loop'}},
        }
    }


def test_build_evidence_report_summarizes_inputs(tmp_path: Path):
    metrics = tmp_path / 'metrics.json'
    evidence = tmp_path / 'evidence_index.json'
    metrics.write_text(json.dumps({'reconnect_count': 2, 'protocol_errors': 1, 'events_logged': 5, 'summaries_published': 3}), encoding='utf-8')
    evidence.write_text(json.dumps({'health': 'degraded', 'last_fault': 'LOW_BAT:warn', 'recent_snapshots': ['a.jpg'], 'recent_events': ['x'], 'last_protocol_issue': 'bad_proto'}), encoding='utf-8')
    report = build_evidence_report(metrics_path=metrics, evidence_index_path=evidence)
    assert report['status'] == 'ready_for_review'
    assert report['reviewGate'] == 'host_runtime_review_ready'
    assert report['finalDeliveryEligible'] is False
    assert report['verificationScope']['targetEnvironmentAcceptancePresent'] is False
    assert 'target_environment_acceptance_artifact_missing' in report['finalDeliveryBlockers']


def test_build_evidence_report_can_mark_final_delivery_eligible_with_verified_target_acceptance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    metrics = tmp_path / 'metrics.json'
    evidence = tmp_path / 'evidence_index.json'
    target = tmp_path / 'target.json'
    metrics.write_text(json.dumps({'events_logged': 3}), encoding='utf-8')
    evidence.write_text(json.dumps({'health': 'good', 'readiness': 'ready'}), encoding='utf-8')
    verification_identity = {
        'profileName': 'target_acceptance',
        'configRoot': '/tmp/config',
        'launchProfilesPath': '/tmp/config/launch_profiles.yaml',
        'configDigest': 'cfg-digest',
        'protocolIdentity': {'webProtocolVersion': '4.1.0', 'schemaVersion': '2026-03-31', 'tcpProtocolVersion': '4.1.0', 'uartProtocolVersion': '4.1.0', 'tcpProtocolDocSha256': 'tcp-doc', 'uartProtocolDocSha256': 'uart-doc'},
        'sourceReleaseIdentity': {'workspaceManifestPath': '/tmp/workspace_manifest.json', 'workspaceManifestSha256': 'manifest-sha'},
        'hardwareIdentity': {},
        'firmwareIdentity': {},
    }
    monkeypatch.setattr('robot_utils.acceptance_bundle.build_verification_identity', lambda **kwargs: verification_identity)
    target.write_text(json.dumps(_verified_target_payload(verification_identity)), encoding='utf-8')
    report = build_evidence_report(metrics_path=metrics, evidence_index_path=evidence, target_environment_acceptance_path=target)
    assert report['verificationScope']['targetEnvironmentAcceptanceVerified'] is True
    assert report['finalDeliveryEligible'] is True
    assert report['finalDeliveryBlockers'] == []


def test_build_evidence_report_marks_unverified_target_acceptance_as_blocked(tmp_path: Path):
    metrics = tmp_path / 'metrics.json'
    evidence = tmp_path / 'evidence_index.json'
    target = tmp_path / 'target.json'
    metrics.write_text(json.dumps({'events_logged': 1}), encoding='utf-8')
    evidence.write_text(json.dumps({'health': 'good', 'readiness': 'ready'}), encoding='utf-8')
    target.write_text(json.dumps({'status': 'ready_host_harness_plus_hardware_probe', 'verificationCoverage': {'hardwareInLoopVerified': False}}), encoding='utf-8')
    report = build_evidence_report(metrics_path=metrics, evidence_index_path=evidence, target_environment_acceptance_path=target)
    assert report['verificationScope']['targetEnvironmentAcceptanceVerified'] is False
    assert 'target_environment_acceptance_not_verified' in report['finalDeliveryBlockers']
    assert report['finalDeliveryEligible'] is False



def test_build_evidence_report_rejects_target_acceptance_with_mismatched_reference_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    metrics = tmp_path / 'metrics.json'
    evidence = tmp_path / 'evidence_index.json'
    target = tmp_path / 'target.json'
    metrics.write_text(json.dumps({'events_logged': 3}), encoding='utf-8')
    evidence.write_text(json.dumps({'health': 'good', 'readiness': 'ready'}), encoding='utf-8')
    artifact_identity = {
        'profileName': 'target_acceptance',
        'configRoot': '/tmp/config',
        'launchProfilesPath': '/tmp/config/launch_profiles.yaml',
        'configDigest': 'cfg-digest',
        'protocolIdentity': {'webProtocolVersion': '4.1.0', 'schemaVersion': '2026-03-31', 'tcpProtocolVersion': '4.1.0', 'uartProtocolVersion': '4.1.0', 'tcpProtocolDocSha256': 'forged-tcp', 'uartProtocolDocSha256': 'forged-uart'},
        'sourceReleaseIdentity': {'workspaceManifestPath': '/tmp/workspace_manifest.json', 'workspaceManifestSha256': 'forged-manifest'},
        'hardwareIdentity': {},
        'firmwareIdentity': {},
    }
    reference_identity = {
        'profileName': 'target_acceptance',
        'configRoot': '/tmp/config',
        'launchProfilesPath': '/tmp/config/launch_profiles.yaml',
        'configDigest': 'cfg-digest',
        'protocolIdentity': {'webProtocolVersion': '4.1.0', 'schemaVersion': '2026-03-31', 'tcpProtocolVersion': '4.1.0', 'uartProtocolVersion': '4.1.0', 'tcpProtocolDocSha256': 'tcp-doc', 'uartProtocolDocSha256': 'uart-doc'},
        'sourceReleaseIdentity': {'workspaceManifestPath': '/tmp/workspace_manifest.json', 'workspaceManifestSha256': 'manifest-sha'},
        'hardwareIdentity': {},
        'firmwareIdentity': {},
    }
    monkeypatch.setattr('robot_utils.acceptance_bundle.build_verification_identity', lambda **kwargs: reference_identity)
    target.write_text(json.dumps(_verified_target_payload(artifact_identity)), encoding='utf-8')
    report = build_evidence_report(metrics_path=metrics, evidence_index_path=evidence, target_environment_acceptance_path=target)
    assert report['verificationScope']['targetEnvironmentAcceptanceVerified'] is False
    assert 'target_environment_acceptance_not_verified' in report['finalDeliveryBlockers']
    assert report['finalDeliveryEligible'] is False
