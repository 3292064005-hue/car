from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robot_utils.acceptance_bundle import build_verification_identity
from robot_utils.verification_evidence import evidence_class_payload


def _write_mock_launch_profile(config_root: Path, *, websocket_overrides: str = '') -> None:
    (config_root / 'launch_profiles.yaml').write_text(
        f'''profiles:
  mock:
    enable_voice: true
    enable_vision: true
    enable_monitor: true
    enable_teleop: true
    use_mock_robot: true
    enable_web_bridge: true
{websocket_overrides}''',
        encoding='utf-8',
    )


def _write_target_acceptance(path: Path, *, repo_root: Path, config_path: str) -> None:
    identity = build_verification_identity(
        repo_root=repo_root,
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


def test_resolve_runtime_surface_config_emits_frontend_env(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
    output = tmp_path / 'resolved.json'
    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'frontend', '--output', str(output)],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['surface'] == 'frontend'
    assert payload['runtimeSurface']['bridgeWebsocketUrl'] == 'ws://127.0.0.1:9001/ws'
    assert payload['runtimeSurface']['apiWebsocketUrl'] == 'ws://127.0.0.1:9100/ws'
    assert payload['frontendEnv']['VITE_ROBOT_WS_URL'] == 'ws://127.0.0.1:9100/ws'
    assert payload['runtimeSurface']['websocketListenHost'] == '127.0.0.1'
    assert payload['runtimeSurface']['apiHealthUrl'] == 'http://127.0.0.1:9100/api/v1/health'
    assert payload['runtimeSurface']['operatorSurfaceContract']['require_operator_ready'] is True
    assert payload['runtimeSurface']['capabilitySnapshot']['web_bridge'] is True
    assert payload['runtimeSurface']['navigationProvider']['resolvedProvider']['providerName'] == 'simple_nav_provider'
    assert payload['runtimeSurface']['navigationProvider']['activationDecision'] == 'activate'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_PROFILE'] == 'mock'
    assert payload['runtimeSurface']['contractArtifactPath'] == str(output.with_suffix('.json'))
    assert payload['frontendEnv']['VITE_ROBOT_SESSION_ROLE'] == 'observer'
    assert payload['frontendEnv']['VITE_ROBOT_SESSION_TOKEN'] == ''
    assert payload['frontendEnv']['VITE_ROBOT_SESSION_ID'] == 'mock-frontend'
    assert json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))['surface'] == 'frontend'


def test_resolve_runtime_surface_config_honors_profile_websocket_overrides(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    _write_mock_launch_profile(
        config_root,
        websocket_overrides='''    bridge_host: 127.0.0.1
    bridge_port: 9000
    mjpeg_url: http://127.0.0.1:8080/stream
    websocket_public_host: 10.0.0.8
    websocket_listen_host: 0.0.0.0
    websocket_port: 9102
    websocket_path: /robot/ws
''',
    )
    output = tmp_path / 'resolved.json'
    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'frontend', '--config-path', str(config_root), '--output', str(output)],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['runtimeSurface']['bridgeWebsocketUrl'] == 'ws://10.0.0.8:9102/robot/ws'
    assert payload['runtimeSurface']['apiWebsocketUrl'] == 'ws://10.0.0.8:9100/ws'
    assert payload['runtimeSurface']['websocketUrl'] == 'ws://10.0.0.8:9100/ws'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_WS_LISTEN_HOST'] == '0.0.0.0'
    assert payload['frontendEnv']['VITE_ROBOT_WS_URL'] == 'ws://10.0.0.8:9100/ws'
    assert payload['frontendEnv']['VITE_ROBOT_SESSION_TOKEN'] == ''


def test_resolve_runtime_surface_config_exposes_packaged_navigation_provider_lane(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    _write_mock_launch_profile(config_root)
    (config_root / 'navigation.yaml').write_text(
        '''robot_navigation:
  ros__parameters:
    provider_name: nav2_provider
''',
        encoding='utf-8',
    )
    output = tmp_path / 'resolved.json'
    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'frontend', '--config-path', str(config_root), '--output', str(output)],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['runtimeSurface']['navigationProvider']['resolvedProvider']['providerName'] == 'nav2_provider'
    assert payload['runtimeSurface']['navigationProvider']['activationDecision'] == 'activate'
    assert payload['runtimeSurface']['navigationProvider']['governanceLane']['packageName'] == 'robot_nav2_adapter'


def test_resolve_runtime_surface_config_structures_accepted_direct_driver_claim(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
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
    _write_target_acceptance(artifact, repo_root=repo_root, config_path=str(config_root))
    output = tmp_path / 'resolved.json'
    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'frontend', '--config-path', str(config_root), '--output', str(output)],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    boundary = payload['runtimeSurface']['hardwareBoundary']
    assert boundary['compatibilitySurfaceRole'] == 'direct_driver'
    assert boundary['activationDecision'] == 'activate'
    assert boundary['validationStatus'] == 'accepted'
    assert boundary['governanceLane']['packageName'] == 'robot_direct_driver'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_ACTIVATION'] == 'activate'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_REJECTION_REASON'] == ''


def test_resolve_runtime_surface_config_exposes_hardware_boundary_snapshot_for_same_package_experimental_lane(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
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
    _write_target_acceptance(artifact, repo_root=repo_root, config_path=str(config_root))
    output = tmp_path / 'resolved.json'
    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'frontend', '--config-path', str(config_root), '--output', str(output)],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    boundary = payload['runtimeSurface']['hardwareBoundary']
    assert boundary['compatibilitySurfaceRole'] == 'direct_driver'
    assert boundary['boardValidationInRepo'] is True
    assert boundary['boardExecutionConfirmed'] is True
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_SURFACE_ROLE'] == 'direct_driver'
    assert boundary['transportAuthority'] == 'ros_process_driver'
    assert boundary['verificationStage'] == 'hardware_in_loop_verified'
    assert boundary['commandTransport'] == 'direct_driver_loop'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_EVIDENCE_CLASS'] == 'hardware_in_loop_verified'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_ACTIVATION'] == 'activate'
