from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robot_utils.acceptance_bundle import build_verification_identity
from robot_navigation.navigation_acceptance import write_navigation_acceptance_artifact
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


def _write_hardware_launch_profile(config_root: Path) -> None:
    (config_root / 'launch_profiles.yaml').write_text(
        '''profiles:
  hardware:
    enable_voice: true
    enable_vision: true
    enable_monitor: true
    enable_teleop: true
    enable_localization: true
    enable_navigation: true
    enable_hardware_interface: true
    enable_api_server: true
    use_mock_robot: false
    enable_web_bridge: true
''',
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


def _write_nav2_acceptance_artifacts(config_root: Path, *, repo_root: Path) -> None:
    simulation = config_root / 'nav2_simulation_smoke.json'
    host = config_root / 'host_harness_acceptance.json'
    switch = config_root / 'nav2_provider_switch_smoke.json'
    docs = config_root / 'nav2_operator_docs_review.json'
    target = config_root / 'target_environment_acceptance.json'
    identity = build_verification_identity(
        repo_root=repo_root,
        config_path=str(config_root),
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
    _write_target_acceptance(target, repo_root=repo_root, config_path=str(config_root))


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
    assert payload['frontendEnv']['VITE_ROBOT_WS_SURFACE_KIND'] == 'api_facade'
    assert payload['frontendEnv']['VITE_ROBOT_WS_AUTHORITY'] == 'authoritative_operator'
    assert payload['runtimeSurface']['websocketListenHost'] == '127.0.0.1'
    assert payload['runtimeSurface']['apiHealthUrl'] == 'http://127.0.0.1:9100/api/v1/health'
    assert payload['runtimeSurface']['operatorSurfaceContract']['require_operator_ready'] is True
    assert payload['runtimeSurface']['capabilitySnapshot']['web_bridge'] is True
    assert payload['runtimeSurface']['standardObservabilityBridgeContract']['enabled'] is False
    assert payload['runtimeSurface']['fleetAdapterBoundaryContract']['enabled'] is False
    assert payload['runtimeSurface']['hardwareBoundary']['compatibilitySurfaceRole'] == 'ros_soft_driver'
    assert payload['runtimeSurface']['hardwareBoundary']['effectiveCompatibilitySurfaceRole'] == 'ros_projection_only'
    assert payload['runtimeSurface']['hardwareBoundary']['effectiveBoardExecutionConfirmed'] is False
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_BOARD_EXECUTION_CONFIRMED'] == 'false'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_EVIDENCE_CLASS'] == 'host_harness_only'
    assert payload['runtimeSurface']['hardwareBoundary']['transportAuthority'] == 'ros_process_driver'
    assert payload['runtimeSurface']['hardwareBoundary']['validationStatus'] == 'downgraded_to_projection'
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
    assert payload['runtimeSurface']['navigationProvider']['activationDecision'] == 'reject'
    assert payload['runtimeSurface']['navigationProvider']['governanceLane']['packageName'] == 'robot_nav2_adapter'
    assert payload['runtimeSurface']['navigationProvider']['selectedRuntimeProvider'] == 'simple_nav_provider'
    assert payload['runtimeSurface']['navigationProvider']['selectedRuntimePackage'] == 'robot_navigation'


def test_resolve_runtime_surface_config_structures_accepted_verified_board_driver_claim(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    _write_hardware_launch_profile(config_root)
    artifact = tmp_path / 'target_environment_acceptance.json'
    (config_root / 'hardware_interface.yaml').write_text(
        f'''robot_hardware_interface:
  ros__parameters:
    compatibility_surface_role: verified_board_driver
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
        [sys.executable, str(script), '--profile', 'hardware', '--surface', 'frontend', '--config-path', str(config_root), '--output', str(output)],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    boundary = payload['runtimeSurface']['hardwareBoundary']
    assert boundary['compatibilitySurfaceRole'] == 'verified_board_driver'
    assert boundary['activationDecision'] == 'activate'
    assert boundary['validationStatus'] == 'accepted'
    assert boundary['governanceLane']['packageName'] == 'robot_direct_driver'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_ACTIVATION'] == 'activate'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_REJECTION_REASON'] == ''
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_BOARD_EXECUTION_CONFIRMED'] == 'true'


def test_resolve_runtime_surface_config_exposes_hardware_boundary_snapshot_for_same_package_experimental_lane(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    _write_hardware_launch_profile(config_root)
    artifact = tmp_path / 'target_environment_acceptance.json'
    (config_root / 'hardware_interface.yaml').write_text(
        f'''robot_hardware_interface:
  ros__parameters:
    compatibility_surface_role: verified_board_driver
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
        [sys.executable, str(script), '--profile', 'hardware', '--surface', 'frontend', '--config-path', str(config_root), '--output', str(output)],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    boundary = payload['runtimeSurface']['hardwareBoundary']
    assert boundary['compatibilitySurfaceRole'] == 'verified_board_driver'
    assert boundary['boardValidationInRepo'] is True
    assert boundary['boardExecutionConfirmed'] is True
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_SURFACE_ROLE'] == 'verified_board_driver'
    assert boundary['transportAuthority'] == 'ros_process_driver'
    assert boundary['verificationStage'] == 'hardware_in_loop_verified'
    assert boundary['commandTransport'] == 'direct_driver_loop'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_EVIDENCE_CLASS'] == 'hardware_in_loop_verified'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_HARDWARE_ACTIVATION'] == 'activate'


def test_resolve_runtime_surface_config_marks_web_bridge_surface_as_observer_only(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
    output = tmp_path / 'resolved.json'
    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'web_bridge', '--output', str(output)],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    surface = payload['runtimeSurface']
    assert surface['websocketSurfaceKind'] == 'bridge_observer'
    assert surface['websocketSurfaceAuthority'] == 'observer_only'


def test_resolve_runtime_surface_config_allows_packaged_navigation_provider_lane_when_explicit_gate_enabled(tmp_path: Path) -> None:
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
    _write_nav2_acceptance_artifacts(config_root, repo_root=repo_root)
    output = tmp_path / 'resolved.json'
    env = dict(os.environ)
    env['ROBOT_ALLOW_EXPERIMENTAL_NAVIGATION_PROVIDER'] = '1'
    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'frontend', '--config-path', str(config_root), '--output', str(output)],
        cwd=str(repo_root),
        env=env,
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['runtimeSurface']['navigationProvider']['activationDecision'] == 'activate'
    assert payload['runtimeSurface']['navigationProvider']['selectedRuntimeProvider'] == 'nav2_provider'
    assert payload['runtimeSurface']['navigationProvider']['experimentalGatePassed'] is True
