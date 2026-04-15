from __future__ import annotations

import json
from pathlib import Path

import pytest

from robot_hardware_interface.hardware_adapter import build_hardware_boundary_snapshot
from robot_utils.acceptance_bundle import build_verification_identity
from robot_utils.verification_evidence import evidence_class_payload

ROOT = Path(__file__).resolve().parents[3]


def _write_target_acceptance(path: Path, *, config_path: str | None = None) -> None:
    identity = build_verification_identity(
        repo_root=ROOT,
        config_path=config_path,
        profile_name='target_acceptance',
        hardware_identity={},
        firmware_identity={},
    )
    path.write_text(
        json.dumps(
            {
                'schemaVersion': 2,
                'artifactType': 'target_environment_acceptance',
                'status': 'target_environment_accepted',
                'passed': True,
                'evidenceClass': evidence_class_payload('hardware_in_loop'),
                'runtime': {'ros2': {'available': True}, 'rclpyAvailable': True},
                'verificationIdentity': identity,
                'verificationCoverage': {
                    'hostHarnessVerified': True,
                    'realBoardObserved': True,
                    'hardwareInLoopVerified': True,
                },
            }
        ),
        encoding='utf-8',
    )


def test_hardware_boundary_defaults_to_projection_only() -> None:
    snapshot = build_hardware_boundary_snapshot(
        compatibility_surface_role='ros_projection_only',
        board_validation_in_repo=False,
        board_execution_confirmed=False,
        feedback_source='external_transport_or_mock',
        actuation_boundary='outside_ros_projection_node',
    )
    payload = snapshot.to_dict()
    assert payload['compatibilitySurfaceRole'] == 'ros_projection_only'
    assert payload['claimScope'] == 'ros_projection_observability_only'
    assert payload['driverIntegrationLane'] == 'projection_only_mainline'
    assert payload['activationDecision'] == 'activate'
    assert payload['validationStatus'] == 'accepted'
    assert payload['governanceLane']['packageName'] == 'robot_hardware_interface'


def test_projection_only_cannot_claim_board_execution() -> None:
    with pytest.raises(ValueError):
        build_hardware_boundary_snapshot(
            compatibility_surface_role='ros_projection_only',
            board_validation_in_repo=True,
            board_execution_confirmed=True,
            feedback_source='external_transport_or_mock',
            actuation_boundary='outside_ros_projection_node',
            verification_stage='hardware_in_loop_verified',
        )


def test_direct_driver_requires_transport_authority_alignment() -> None:
    with pytest.raises(ValueError):
        build_hardware_boundary_snapshot(
            compatibility_surface_role='direct_driver',
            board_validation_in_repo=False,
            board_execution_confirmed=False,
            feedback_source='direct_board_feedback',
            actuation_boundary='inside_ros_driver',
            transport_authority='external_board_controller',
        )


def test_direct_driver_hil_claim_requires_acceptance_artifact() -> None:
    with pytest.raises(ValueError):
        build_hardware_boundary_snapshot(
            compatibility_surface_role='direct_driver',
            board_validation_in_repo=True,
            board_execution_confirmed=True,
            feedback_source='direct_board_feedback',
            actuation_boundary='inside_ros_driver',
            transport_authority='ros_process_driver',
            verification_stage='hardware_in_loop_verified',
            command_transport='direct_driver_loop',
        )


def test_direct_driver_lane_accepts_separate_package_when_artifact_exists(tmp_path: Path) -> None:
    artifact = tmp_path / 'target_environment_acceptance.json'
    _write_target_acceptance(artifact)

    snapshot = build_hardware_boundary_snapshot(
        compatibility_surface_role='direct_driver',
        board_validation_in_repo=True,
        board_execution_confirmed=True,
        feedback_source='direct_board_feedback',
        actuation_boundary='inside_ros_driver',
        transport_authority='ros_process_driver',
        verification_stage='hardware_in_loop_verified',
        command_transport='direct_driver_loop',
        verification_artifact_path=str(artifact),
    )
    payload = snapshot.to_dict()
    assert payload['compatibilitySurfaceRole'] == 'direct_driver'
    assert payload['boardExecutionConfirmed'] is True
    assert payload['verificationArtifactType'] == 'target_environment_acceptance'
    assert payload['executionEvidenceClass'] == 'hardware_in_loop_verified'
    assert payload['activationDecision'] == 'activate'
    assert payload['validationStatus'] == 'accepted'
    assert payload['directDriverMainlineAllowed'] is True
    assert payload['governanceLane']['packageName'] == 'robot_direct_driver'


def test_direct_driver_same_package_experimental_mode_still_accepted(tmp_path: Path) -> None:
    artifact = tmp_path / 'target_environment_acceptance.json'
    _write_target_acceptance(artifact)
    snapshot = build_hardware_boundary_snapshot(
        compatibility_surface_role='direct_driver',
        board_validation_in_repo=True,
        board_execution_confirmed=True,
        feedback_source='direct_board_feedback',
        actuation_boundary='inside_ros_driver',
        transport_authority='ros_process_driver',
        verification_stage='hardware_in_loop_verified',
        command_transport='direct_driver_loop',
        verification_artifact_path=str(artifact),
        direct_driver_lane_policy='same_package_experimental',
    )
    payload = snapshot.to_dict()
    assert payload['compatibilitySurfaceRole'] == 'direct_driver'
    assert payload['directDriverMainlineAllowed'] is True
