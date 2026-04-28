from __future__ import annotations

import json
from pathlib import Path

from robot_navigation.navigation_acceptance import write_navigation_acceptance_artifact
from robot_navigation.provider_contract import (
    ensure_provider_runtime_supported,
    navigation_provider_activation,
    navigation_provider_registry_payload,
    resolve_navigation_provider,
)
from robot_utils.acceptance_bundle import build_verification_identity
from robot_utils.verification_evidence import evidence_class_payload


def _write_nav2_acceptance_artifacts(root: Path) -> dict[str, str]:
    repo_root = Path(__file__).resolve().parents[3]
    simulation = root / 'nav2_simulation_smoke.json'
    host = root / 'host_harness_acceptance.json'
    switch = root / 'nav2_provider_switch_smoke.json'
    docs = root / 'nav2_operator_docs_review.json'
    target = root / 'target_environment_acceptance.json'
    identity = build_verification_identity(
        repo_root=repo_root,
        config_path=str(root),
        profile_name='target_acceptance',
        hardware_identity={},
        firmware_identity={},
    )
    write_navigation_acceptance_artifact(simulation, {
        'schemaVersion': 1,
        'artifactType': 'nav2_simulation_smoke',
        'providerName': 'nav2_provider',
        'passed': True,
        'testsExecuted': ['test_nav2_adapter_node.py'],
    })
    write_navigation_acceptance_artifact(host, {
        'schemaVersion': 2,
        'artifactType': 'host_harness_acceptance',
        'passed': True,
        'verificationIdentity': identity,
        'evidenceClass': evidence_class_payload('integration_live_ros_mock_robot'),
    })
    write_navigation_acceptance_artifact(switch, {
        'schemaVersion': 1,
        'artifactType': 'nav2_provider_switch_smoke',
        'providerName': 'nav2_provider',
        'passed': True,
        'switchSequence': ['nav2_provider', 'simple_nav_provider'],
    })
    write_navigation_acceptance_artifact(docs, {
        'schemaVersion': 1,
        'artifactType': 'operator_docs_review',
        'providerName': 'nav2_provider',
        'passed': True,
        'docsPaths': ['ros2_ws/src/robot_nav2_adapter/README.md'],
        'requiredMentions': ['ROBOT_ALLOW_EXPERIMENTAL_NAVIGATION_PROVIDER=1'],
    })
    target.write_text(json.dumps({
        'schemaVersion': 2,
        'artifactType': 'target_environment_acceptance',
        'status': 'target_environment_accepted',
        'passed': True,
        'evidenceClass': evidence_class_payload('hardware_in_loop'),
        'verificationIdentity': identity,
        'runtime': {'ros2': {'available': True}, 'rclpyAvailable': True},
        'verificationCoverage': {'hostHarnessVerified': True, 'realBoardObserved': True, 'hardwareInLoopVerified': True},
    }, indent=2), encoding='utf-8')
    return {
        'simulation_smoke': str(simulation),
        'host_harness_smoke': str(host),
        'provider_switch_smoke': str(switch),
        'operator_docs_review': str(docs),
        'target_environment_acceptance': str(target),
    }


def test_nav2_provider_is_governed_local_adapter_runtime_and_remains_experimental(tmp_path: Path) -> None:
    provider = resolve_navigation_provider('nav2_provider')
    artifacts = _write_nav2_acceptance_artifacts(tmp_path)
    activation = navigation_provider_activation(
        'nav2_provider',
        allow_experimental=True,
        acceptance_artifact_paths=artifacts,
        reference_config_path=str(tmp_path),
    )
    assert provider.implemented is True
    assert provider.integration_stage == 'governed_local_adapter_runtime'
    assert provider.activation_policy == 'experimental_local_adapter_requires_explicit_gate'
    assert 'health' in provider.capabilities
    assert 'planner' not in provider.capabilities
    assert activation['providerVisibility'] == 'experimental'
    assert activation['runtimeSupported'] is True
    assert activation['activationDecision'] == 'activate'
    assert activation['blockingReason'] is None
    assert activation['acceptanceGatePassed'] is True
    assert activation['backendIntegrated'] is False
    assert activation['capabilityTruth']['implementationStatus'] == 'governed_local_adapter_runtime'
    assert activation['governanceLane']['packageName'] == 'robot_nav2_adapter'
    assert activation['governanceBoundary']['boundaryRole'] == 'governed_adapter_boundary'
    assert activation['selectedGovernanceBoundary']['adapterRuntime'] is True
    assert activation['selectedRuntimeProvider'] == 'nav2_provider'
    assert activation['selectedRuntimePackage'] == 'robot_nav2_adapter'
    assert activation['selectedRuntimeExecutable'] == 'nav2_adapter_node'
    assert activation['selectedRuntimeReason'] == 'requested_provider_runtime_available'


def test_simple_provider_remains_runtime_supported() -> None:
    provider = resolve_navigation_provider('simple_nav_provider')
    assert ensure_provider_runtime_supported(provider) is provider


def test_nav2_provider_runtime_support_guard_accepts_isolated_lane_package() -> None:
    provider = resolve_navigation_provider('nav2_provider')
    assert ensure_provider_runtime_supported(provider) is provider


def test_navigation_provider_registry_only_exposes_mainline_supported_backends() -> None:
    registry = navigation_provider_registry_payload()
    assert set(registry) == {'simple_nav_provider'}


def test_nav2_provider_requires_explicit_experimental_gate_by_default() -> None:
    activation = navigation_provider_activation('nav2_provider')
    assert activation['runtimeSupported'] is True
    assert activation['activationDecision'] == 'reject'
    assert activation['blockingReason'] == 'experimental_provider_requires_explicit_allow_flag'
    assert activation['selectedRuntimeProvider'] == 'simple_nav_provider'


def test_nav2_provider_requires_acceptance_artifacts_even_when_gate_enabled(tmp_path: Path) -> None:
    artifacts = _write_nav2_acceptance_artifacts(tmp_path)
    Path(artifacts['target_environment_acceptance']).unlink()
    activation = navigation_provider_activation(
        'nav2_provider',
        allow_experimental=True,
        acceptance_artifact_paths=artifacts,
        reference_config_path=str(tmp_path),
    )
    assert activation['activationDecision'] == 'reject'
    assert activation['blockingReason'] == 'experimental_provider_acceptance_artifacts_incomplete'
    assert activation['acceptanceGatePassed'] is False
    assert activation['selectedRuntimeProvider'] == 'simple_nav_provider'
