from __future__ import annotations

import json
from pathlib import Path

from robot_navigation.navigation_acceptance import nav2_external_backend_smoke_required, validate_nav2_acceptance_gate, write_navigation_acceptance_artifact
from robot_navigation.provider_contract import navigation_provider_activation
from robot_utils.acceptance_bundle import build_verification_identity
from robot_utils.verification_evidence import evidence_class_payload


def _write_base_artifacts(tmp_path: Path) -> dict[str, str]:
    identity = build_verification_identity(repo_root=Path(__file__).resolve().parents[3], config_path=str(tmp_path), profile_name='target_acceptance', hardware_identity={}, firmware_identity={})
    simulation = tmp_path / 'nav2_simulation_smoke.json'
    host = tmp_path / 'host_harness_acceptance.json'
    switch = tmp_path / 'nav2_provider_switch_smoke.json'
    docs = tmp_path / 'nav2_operator_docs_review.json'
    target = tmp_path / 'target_environment_acceptance.json'
    write_navigation_acceptance_artifact(simulation, {'schemaVersion': 1, 'artifactType': 'nav2_simulation_smoke', 'providerName': 'nav2_provider', 'passed': True, 'testsExecuted': ['test_nav2_adapter_node.py']})
    write_navigation_acceptance_artifact(host, {'schemaVersion': 2, 'artifactType': 'host_harness_acceptance', 'passed': True, 'verificationIdentity': identity, 'evidenceClass': evidence_class_payload('integration_live_ros_mock_robot')})
    write_navigation_acceptance_artifact(switch, {'schemaVersion': 1, 'artifactType': 'nav2_provider_switch_smoke', 'providerName': 'nav2_provider', 'passed': True, 'switchSequence': ['nav2_provider', 'simple_nav_provider']})
    write_navigation_acceptance_artifact(docs, {'schemaVersion': 1, 'artifactType': 'operator_docs_review', 'providerName': 'nav2_provider', 'passed': True, 'docsPaths': ['ros2_ws/src/robot_nav2_adapter/README.md'], 'requiredMentions': ['ROBOT_ALLOW_EXPERIMENTAL_NAVIGATION_PROVIDER=1']})
    target.write_text(json.dumps({'schemaVersion': 2, 'artifactType': 'target_environment_acceptance', 'status': 'target_environment_accepted', 'passed': True, 'evidenceClass': evidence_class_payload('hardware_in_loop'), 'verificationIdentity': identity, 'runtime': {'ros2': {'available': True}, 'rclpyAvailable': True}, 'verificationCoverage': {'hostHarnessVerified': True, 'realBoardObserved': True, 'hardwareInLoopVerified': True}}, indent=2), encoding='utf-8')
    return {'simulation_smoke': str(simulation), 'host_harness_smoke': str(host), 'provider_switch_smoke': str(switch), 'operator_docs_review': str(docs), 'target_environment_acceptance': str(target)}


def test_external_backend_smoke_gate_is_required_when_external_backend_is_integrated(tmp_path: Path) -> None:
    artifacts = _write_base_artifacts(tmp_path)
    assert nav2_external_backend_smoke_required({'external_nav2_backend_integrated': True}) is True
    gate = validate_nav2_acceptance_gate(artifacts, config_root=tmp_path, require_external_backend_smoke=True)
    assert gate.valid is False
    assert 'missing_path_external_backend_smoke' in gate.errors


def test_navigation_provider_activation_requires_external_backend_smoke_when_external_backend_claimed(tmp_path: Path) -> None:
    artifacts = _write_base_artifacts(tmp_path)
    activation = navigation_provider_activation('nav2_provider', allow_experimental=True, acceptance_artifact_paths=artifacts, reference_config_path=str(tmp_path), require_external_backend_smoke=True)
    assert activation['activationDecision'] == 'reject'
    assert activation['requireExternalBackendSmoke'] is True
    assert activation['acceptanceGatePassed'] is False


def test_external_backend_smoke_gate_passes_with_valid_artifact(tmp_path: Path) -> None:
    artifacts = _write_base_artifacts(tmp_path)
    external = tmp_path / 'nav2_external_backend_smoke.json'
    write_navigation_acceptance_artifact(external, {'schemaVersion': 1, 'artifactType': 'nav2_external_backend_smoke', 'providerName': 'nav2_provider', 'selectedBackend': 'external_nav2_stack', 'backendIntegrated': True, 'passed': True})
    artifacts['external_backend_smoke'] = str(external)
    gate = validate_nav2_acceptance_gate(artifacts, config_root=tmp_path, require_external_backend_smoke=True)
    assert gate.valid is True
