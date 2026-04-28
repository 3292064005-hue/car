from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[3] / 'scripts' / 'capture_target_environment_acceptance.py'
SPEC = importlib.util.spec_from_file_location('capture_target_environment_acceptance', SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault('capture_target_environment_acceptance', MODULE)
SPEC.loader.exec_module(MODULE)


def _write_acceptance_artifact(path: Path, *, artifact_type: str, passed: bool, evidence_key: str, hardware: bool = False, firmware: bool = False) -> None:
    verification_identity = {
        'profileName': 'target_acceptance',
        'configRoot': '/tmp/config',
        'launchProfilesPath': '/tmp/config/launch_profiles.yaml',
        'configDigest': 'cfg-digest',
        'protocolIdentity': {
            'webProtocolVersion': '4.1.0',
            'schemaVersion': '2026-03-31',
            'tcpProtocolVersion': '4.1.0',
            'uartProtocolVersion': '4.1.0',
            'tcpProtocolDocSha256': 'tcp-doc',
            'uartProtocolDocSha256': 'uart-doc',
        },
        'sourceReleaseIdentity': {
            'workspaceManifestPath': '/tmp/workspace_manifest.json',
            'workspaceManifestSha256': 'manifest-sha',
            'workspaceId': 'single_root_canonical:manifest',
            'artifactId': 'inspection_robot_source:artifact',
            'sourceTreeSha256': 'source-sha',
            'layoutMode': 'single_root_canonical',
            'includedFileCount': 1,
        },
        'hardwareIdentity': {'boardId': 'board-a', 'boardClass': 'xmate'} if hardware else {},
        'firmwareIdentity': {'firmwareVersion': '1.0.0', 'firmwareSha256': 'fw-sha'} if firmware else {},
    }
    path.write_text(
        json.dumps(
            {
                'schemaVersion': 2,
                'artifactType': artifact_type,
                'status': 'passed' if passed else 'failed',
                'passed': passed,
                'evidenceClass': {'key': evidence_key},
                'verificationIdentity': verification_identity,
            }
        ),
        encoding='utf-8',
    )


def _identity(*, hardware_identity=None, firmware_identity=None) -> dict:
    return {
        'profileName': 'target_acceptance',
        'configRoot': '/tmp/config',
        'launchProfilesPath': '/tmp/config/launch_profiles.yaml',
        'configDigest': 'cfg-digest',
        'protocolIdentity': {
            'webProtocolVersion': '4.1.0',
            'schemaVersion': '2026-03-31',
            'tcpProtocolVersion': '4.1.0',
            'uartProtocolVersion': '4.1.0',
            'tcpProtocolDocSha256': 'tcp-doc',
            'uartProtocolDocSha256': 'uart-doc',
        },
        'sourceReleaseIdentity': {
            'workspaceManifestPath': '/tmp/workspace_manifest.json',
            'workspaceManifestSha256': 'manifest-sha',
            'workspaceId': 'single_root_canonical:manifest',
            'artifactId': 'inspection_robot_source:artifact',
            'sourceTreeSha256': 'source-sha',
            'layoutMode': 'single_root_canonical',
            'includedFileCount': 1,
        },
        'hardwareIdentity': dict(hardware_identity or {}),
        'firmwareIdentity': dict(firmware_identity or {}),
    }


def test_capture_target_environment_acceptance_writes_expected_payload(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / 'target_environment_acceptance.json'
    manifest_path = tmp_path / 'release_quality_manifest.json'
    manifest_path.write_text('{"status": "ready_operator_e2e_mock_robot"}\n', encoding='utf-8')

    monkeypatch.setattr(MODULE, '_command_output', lambda *args: {'available': True, 'path': f'/usr/bin/{args[0]}', 'output': 'mock-version'})
    monkeypatch.setattr(MODULE.importlib.util, 'find_spec', lambda name: object() if name == 'rclpy' else None)
    monkeypatch.setattr(MODULE, '_read_os_release', lambda: {'PRETTY_NAME': 'Ubuntu 22.04'})
    monkeypatch.setattr(MODULE, 'build_verification_identity', lambda **kwargs: _identity(hardware_identity=kwargs.get('hardware_identity'), firmware_identity=kwargs.get('firmware_identity')))

    exit_code = MODULE.main(['--output', str(output_path), '--quality-manifest', str(manifest_path)])
    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['status'] == 'ready_runtime_evidence_incomplete'
    assert payload['verificationCoverage']['hardwareInLoopVerified'] is False
    assert payload['verificationCoverage']['hardwareInLoopArtifactPresent'] is False


def test_capture_target_environment_acceptance_only_marks_host_harness_verified_when_reports_pass(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / 'target_environment_acceptance.json'
    host_report = tmp_path / 'host_harness_acceptance.json'
    real_board_report = tmp_path / 'real_board_acceptance.json'
    _write_acceptance_artifact(host_report, artifact_type='host_harness_acceptance', passed=True, evidence_key='integration_live_ros_mock_robot')
    _write_acceptance_artifact(real_board_report, artifact_type='real_board_acceptance', passed=False, evidence_key='hardware_probe_observational', hardware=True)

    monkeypatch.setattr(MODULE, '_command_output', lambda *args: {'available': True, 'path': f'/usr/bin/{args[0]}', 'output': 'mock-version'})
    monkeypatch.setattr(MODULE.importlib.util, 'find_spec', lambda name: object() if name == 'rclpy' else None)
    monkeypatch.setattr(MODULE, '_read_os_release', lambda: {'PRETTY_NAME': 'Ubuntu 22.04'})
    monkeypatch.setattr(MODULE, 'build_verification_identity', lambda **kwargs: _identity(hardware_identity=kwargs.get('hardware_identity'), firmware_identity=kwargs.get('firmware_identity')))

    exit_code = MODULE.main(['--output', str(output_path), '--host-harness-report', str(host_report), '--real-board-report', str(real_board_report)])
    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['verificationCoverage']['status'] == 'ready_host_harness_only'


def test_capture_target_environment_acceptance_requires_strong_hil_artifact_for_accepted_status(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / 'target_environment_acceptance.json'
    host_report = tmp_path / 'host_harness_acceptance.json'
    real_board_report = tmp_path / 'real_board_acceptance.json'
    hil_report = tmp_path / 'hardware_in_loop_acceptance.json'
    _write_acceptance_artifact(host_report, artifact_type='host_harness_acceptance', passed=True, evidence_key='integration_live_ros_mock_robot')
    _write_acceptance_artifact(real_board_report, artifact_type='real_board_acceptance', passed=True, evidence_key='hardware_probe_observational', hardware=True)
    _write_acceptance_artifact(hil_report, artifact_type='hardware_in_loop_acceptance', passed=True, evidence_key='hardware_in_loop', hardware=True, firmware=True)

    monkeypatch.setattr(MODULE, '_command_output', lambda *args: {'available': True, 'path': f'/usr/bin/{args[0]}', 'output': 'mock-version'})
    monkeypatch.setattr(MODULE.importlib.util, 'find_spec', lambda name: object() if name == 'rclpy' else None)
    monkeypatch.setattr(MODULE, '_read_os_release', lambda: {'PRETTY_NAME': 'Ubuntu 22.04'})
    monkeypatch.setattr(MODULE, 'build_verification_identity', lambda **kwargs: _identity(hardware_identity=kwargs.get('hardware_identity'), firmware_identity=kwargs.get('firmware_identity')))

    exit_code = MODULE.main([
        '--output',
        str(output_path),
        '--host-harness-report',
        str(host_report),
        '--real-board-report',
        str(real_board_report),
        '--hardware-in-loop-report',
        str(hil_report),
    ])
    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['verificationCoverage']['hardwareInLoopVerified'] is True
    assert payload['verificationCoverage']['status'] == 'target_environment_accepted'
    assert payload['status'] == 'target_environment_accepted'



def test_capture_target_environment_acceptance_rejects_artifacts_with_mismatched_reference_identity(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / 'target_environment_acceptance.json'
    host_report = tmp_path / 'host_harness_acceptance.json'
    real_board_report = tmp_path / 'real_board_acceptance.json'
    hil_report = tmp_path / 'hardware_in_loop_acceptance.json'
    _write_acceptance_artifact(host_report, artifact_type='host_harness_acceptance', passed=True, evidence_key='integration_live_ros_mock_robot')
    _write_acceptance_artifact(real_board_report, artifact_type='real_board_acceptance', passed=True, evidence_key='hardware_probe_observational', hardware=True)
    _write_acceptance_artifact(hil_report, artifact_type='hardware_in_loop_acceptance', passed=True, evidence_key='hardware_in_loop', hardware=True, firmware=True)

    def _forged(path: Path) -> None:
        payload = json.loads(path.read_text(encoding='utf-8'))
        payload['verificationIdentity']['protocolIdentity']['tcpProtocolDocSha256'] = 'forged-tcp'
        payload['verificationIdentity']['protocolIdentity']['uartProtocolDocSha256'] = 'forged-uart'
        payload['verificationIdentity']['sourceReleaseIdentity']['workspaceManifestSha256'] = 'forged-manifest'
        payload['verificationIdentity']['sourceReleaseIdentity']['sourceTreeSha256'] = 'forged-source-sha'
        path.write_text(json.dumps(payload), encoding='utf-8')

    _forged(host_report)
    _forged(real_board_report)
    _forged(hil_report)

    monkeypatch.setattr(MODULE, '_command_output', lambda *args: {'available': True, 'path': f'/usr/bin/{args[0]}', 'output': 'mock-version'})
    monkeypatch.setattr(MODULE.importlib.util, 'find_spec', lambda name: object() if name == 'rclpy' else None)
    monkeypatch.setattr(MODULE, '_read_os_release', lambda: {'PRETTY_NAME': 'Ubuntu 22.04'})
    monkeypatch.setattr(MODULE, 'build_verification_identity', lambda **kwargs: _identity(hardware_identity=kwargs.get('hardware_identity'), firmware_identity=kwargs.get('firmware_identity')))

    exit_code = MODULE.main([
        '--output', str(output_path),
        '--host-harness-report', str(host_report),
        '--real-board-report', str(real_board_report),
        '--hardware-in-loop-report', str(hil_report),
    ])
    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['verificationCoverage']['hostHarnessObserved'] is False
    assert payload['verificationCoverage']['realBoardObserved'] is False
    assert payload['verificationCoverage']['hardwareInLoopVerified'] is False
    assert payload['status'] != 'target_environment_accepted'
    assert 'tcp_protocol_identity_mismatch:reference' in payload['verificationCoverage']['validationErrors']['identity']
