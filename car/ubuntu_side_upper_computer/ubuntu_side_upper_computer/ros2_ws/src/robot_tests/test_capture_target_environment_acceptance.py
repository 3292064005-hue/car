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


def test_capture_target_environment_acceptance_writes_expected_payload(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / 'target_environment_acceptance.json'
    manifest_path = tmp_path / 'release_quality_manifest.json'
    manifest_path.write_text('{"status": "ready_for_release"}\n', encoding='utf-8')

    monkeypatch.setattr(MODULE, '_command_output', lambda *args: {'available': True, 'path': f'/usr/bin/{args[0]}', 'output': 'mock-version'})
    monkeypatch.setattr(MODULE.importlib.util, 'find_spec', lambda name: object() if name == 'rclpy' else None)
    monkeypatch.setattr(MODULE, '_read_os_release', lambda: {'PRETTY_NAME': 'Ubuntu 22.04'})

    exit_code = MODULE.main([
        '--output',
        str(output_path),
        '--quality-manifest',
        str(manifest_path),
    ])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['status'] == 'ready_runtime_evidence_incomplete'
    assert payload['runtime']['ros2']['available'] is True
    assert payload['runtime']['rclpyAvailable'] is True
    assert payload['artifacts']['releaseQualityManifest']['exists'] is True
    assert payload['artifacts']['releaseQualityManifest']['path'] == str(manifest_path)
    assert payload['verificationCoverage']['hostHarnessEvidenceClass']['key'] == 'integration_live_ros_mock_robot'
    assert payload['verificationCoverage']['realBoardEvidenceClass']['key'] == 'hardware_probe_observational'


def test_capture_target_environment_acceptance_only_marks_verified_when_reports_pass(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / 'target_environment_acceptance.json'
    host_report = tmp_path / 'host_harness_acceptance.json'
    real_board_report = tmp_path / 'real_board_acceptance.json'
    host_report.write_text('{"passed": true}\n', encoding='utf-8')
    real_board_report.write_text('{"passed": false}\n', encoding='utf-8')

    monkeypatch.setattr(MODULE, '_command_output', lambda *args: {'available': True, 'path': f'/usr/bin/{args[0]}', 'output': 'mock-version'})
    monkeypatch.setattr(MODULE.importlib.util, 'find_spec', lambda name: object() if name == 'rclpy' else None)
    monkeypatch.setattr(MODULE, '_read_os_release', lambda: {'PRETTY_NAME': 'Ubuntu 22.04'})

    exit_code = MODULE.main([
        '--output',
        str(output_path),
        '--host-harness-report',
        str(host_report),
        '--real-board-report',
        str(real_board_report),
    ])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['verificationCoverage']['hostHarnessVerified'] is True
    assert payload['verificationCoverage']['realBoardVerified'] is False
    assert payload['verificationCoverage']['realBoardArtifactPresent'] is True
    assert payload['verificationCoverage']['status'] == 'ready_host_harness_only'
    assert payload['status'] == 'ready_host_harness_only'


def test_capture_target_environment_acceptance_distinguishes_hardware_probe_from_verified(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / 'target_environment_acceptance.json'
    host_report = tmp_path / 'host_harness_acceptance.json'
    real_board_report = tmp_path / 'real_board_acceptance.json'
    host_report.write_text('{"passed": true}\n', encoding='utf-8')
    real_board_report.write_text('{"passed": true}\n', encoding='utf-8')

    monkeypatch.setattr(MODULE, '_command_output', lambda *args: {'available': True, 'path': f'/usr/bin/{args[0]}', 'output': 'mock-version'})
    monkeypatch.setattr(MODULE.importlib.util, 'find_spec', lambda name: object() if name == 'rclpy' else None)
    monkeypatch.setattr(MODULE, '_read_os_release', lambda: {'PRETTY_NAME': 'Ubuntu 22.04'})

    exit_code = MODULE.main([
        '--output',
        str(output_path),
        '--host-harness-report',
        str(host_report),
        '--real-board-report',
        str(real_board_report),
    ])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['verificationCoverage']['status'] == 'ready_host_harness_plus_hardware_probe'
    assert payload['status'] == 'ready_host_harness_plus_hardware_probe'
    assert payload['verificationCoverage']['realBoardEvidenceClass']['key'] == 'hardware_probe_observational'


def test_capture_target_environment_acceptance_allows_probe_only_status(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / 'target_environment_acceptance.json'
    real_board_report = tmp_path / 'real_board_acceptance.json'
    real_board_report.write_text('{"passed": true}\n', encoding='utf-8')

    monkeypatch.setattr(MODULE, '_command_output', lambda *args: {'available': True, 'path': f'/usr/bin/{args[0]}', 'output': 'mock-version'})
    monkeypatch.setattr(MODULE.importlib.util, 'find_spec', lambda name: object() if name == 'rclpy' else None)
    monkeypatch.setattr(MODULE, '_read_os_release', lambda: {'PRETTY_NAME': 'Ubuntu 22.04'})

    exit_code = MODULE.main([
        '--output',
        str(output_path),
        '--real-board-report',
        str(real_board_report),
    ])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['verificationCoverage']['status'] == 'ready_hardware_probe_only'
    assert payload['status'] == 'ready_hardware_probe_only'
