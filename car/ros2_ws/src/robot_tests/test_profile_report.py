from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.render_profile_report import build_report
from robot_utils.acceptance_bundle import build_verification_identity
from robot_utils.verification_evidence import evidence_class_payload


def _write_target_acceptance(path: Path, *, config_path: str) -> None:
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


def _write_mock_launch_profile(config_root: Path) -> None:
    (config_root / 'launch_profiles.yaml').write_text(
        '''profiles:
  mock:
    enable_voice: true
    enable_vision: true
    enable_monitor: true
    enable_teleop: true
    use_mock_robot: true
    enable_web_bridge: true
''',
        encoding='utf-8',
    )


def test_profile_report_contains_enabled_nodes() -> None:
    report = build_report('dev')
    profile = report['profile']
    assert profile['name'] == 'dev'
    assert 'robot_bridge' in profile['enabled_nodes']
    assert 'robot_monitor' in profile['enabled_nodes']
    assert report['required_configs']


def test_profile_report_contains_dependency_plan_and_runtime_policy() -> None:
    report = build_report('hardware')
    assert report['dependency_plan']['surface'] == 'backend'
    assert report['runtime_policy']['preferred_runtime'] == 'split_runtime'
    assert report['capability_snapshot']['web_bridge'] is True
    assert report['navigation_provider']['resolvedProvider']['providerName'] == 'simple_nav_provider'


def test_profile_report_accepts_separate_package_direct_driver_lane(tmp_path: Path) -> None:
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    _write_mock_launch_profile(config_root)
    artifact = tmp_path / 'target_environment_acceptance.json'
    (config_root / 'hardware_interface.yaml').write_text(
        f'''robot_hardware_interface:
  ros__parameters:
    compatibility_surface_role: direct_driver
    board_validation_in_repo: true
    board_execution_confirmed: true
    feedback_source: direct_board_feedback
    actuation_boundary: inside_ros_driver
    transport_authority: ros_process_driver
    verification_stage: hardware_in_loop_verified
    command_transport: direct_driver_loop
    verification_artifact_path: {artifact}
''',
        encoding='utf-8',
    )
    _write_target_acceptance(artifact, config_path=str(config_root))
    report = build_report('mock', config_path=str(config_root))
    boundary = report['hardware_boundary']
    assert boundary['compatibilitySurfaceRole'] == 'direct_driver'
    assert boundary['activationDecision'] == 'activate'
    assert boundary['validationStatus'] == 'accepted'
    assert boundary['governanceLane']['packageName'] == 'robot_direct_driver'
    assert boundary['commandTransport'] == 'direct_driver_loop'


def test_profile_report_accepts_explicit_same_package_experimental_direct_driver_lane(tmp_path: Path) -> None:
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    _write_mock_launch_profile(config_root)
    artifact = tmp_path / 'target_environment_acceptance.json'
    (config_root / 'hardware_interface.yaml').write_text(
        f'''robot_hardware_interface:
  ros__parameters:
    compatibility_surface_role: direct_driver
    board_validation_in_repo: true
    board_execution_confirmed: true
    feedback_source: direct_board_feedback
    actuation_boundary: inside_ros_driver
    transport_authority: ros_process_driver
    verification_stage: hardware_in_loop_verified
    command_transport: direct_driver_loop
    verification_artifact_path: {artifact}
    direct_driver_lane_policy: same_package_experimental
''',
        encoding='utf-8',
    )
    _write_target_acceptance(artifact, config_path=str(config_root))
    report = build_report('mock', config_path=str(config_root))
    boundary = report['hardware_boundary']
    assert boundary['compatibilitySurfaceRole'] == 'direct_driver'
    assert boundary['boardValidationInRepo'] is True
    assert boundary['boardExecutionConfirmed'] is True
    assert boundary['feedbackSource'] == 'direct_board_feedback'
    assert boundary['actuationBoundary'] == 'inside_ros_driver'
    assert boundary['transportAuthority'] == 'ros_process_driver'
    assert boundary['verificationStage'] == 'hardware_in_loop_verified'
    assert boundary['commandTransport'] == 'direct_driver_loop'
    assert boundary['verificationArtifactType'] == 'target_environment_acceptance'
    assert boundary['activationDecision'] == 'activate'
    assert boundary['validationStatus'] == 'accepted'
