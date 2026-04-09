#!/usr/bin/env python3
"""Capture target-environment acceptance evidence for a completed release verification run.

The report produced by this script accompanies a live ROS 2 Humble verification
run executed on the target delivery environment. It records host/runtime
metadata together with the key verification artifacts produced by
``run_release_verification.sh`` while keeping observational probe evidence
separate from behavior-level hardware-in-loop claims.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from typing import Any

from runtime_artifacts import describe_file, extend_ros_import_path

extend_ros_import_path()

from robot_utils.acceptance_bundle import (
    ACCEPTANCE_SCHEMA_VERSION,
    acceptance_identity_match,
    acceptance_identity_matches_reference,
    build_verification_identity,
    validate_acceptance_artifact,
)
from robot_utils.verification_evidence import evidence_class_payload, strongest_evidence_class


def _read_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    path = Path('/etc/os-release')
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        data[key] = value.strip().strip('"')
    return data


def _command_output(*args: str) -> dict[str, Any]:
    executable = shutil.which(args[0])
    if executable is None:
        return {'available': False, 'path': None, 'output': None}
    try:
        completed = subprocess.run(args, check=True, capture_output=True, text=True, timeout=15.0)
        output = (completed.stdout or completed.stderr).strip() or None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        output = str(exc)
    return {'available': True, 'path': executable, 'output': output}


def _load_json_file(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _coverage_status(*, ros2_available: bool, rclpy_available: bool, host_harness_valid: bool, real_board_valid: bool, hardware_in_loop_valid: bool) -> str:
    if ros2_available and rclpy_available and host_harness_valid and real_board_valid and hardware_in_loop_valid:
        return 'target_environment_accepted'
    if ros2_available and rclpy_available and host_harness_valid and real_board_valid:
        return 'ready_host_harness_plus_hardware_probe'
    if ros2_available and rclpy_available and real_board_valid:
        return 'ready_hardware_probe_only'
    if ros2_available and rclpy_available and host_harness_valid:
        return 'ready_host_harness_only'
    if ros2_available and rclpy_available:
        return 'ready_runtime_evidence_incomplete'
    return 'incomplete_runtime'


def _claim_boundary(*, host_harness_valid: bool, real_board_valid: bool, hardware_in_loop_valid: bool) -> dict[str, Any]:
    observed_classes = ['unit_stubbed']
    if host_harness_valid:
        observed_classes.append('integration_live_ros_mock_robot')
    if real_board_valid:
        observed_classes.append('hardware_probe_observational')
    if hardware_in_loop_valid:
        observed_classes.append('hardware_in_loop')
    strongest = strongest_evidence_class(observed_classes)
    return {
        'highestObservedEvidenceClass': evidence_class_payload(strongest),
        'supportedClaims': list(evidence_class_payload(strongest)['supportedClaims']),
        'notes': [
            'realBoardObserved only means an observational live-runtime probe artifact passed schema and identity checks',
            'realBoardVerified stays false until behavior-level hardware-in-loop evidence is supplied and identities match',
            'hostHarnessObserved does not imply direct real-board behavior verification',
        ],
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Capture target environment acceptance evidence.')
    parser.add_argument('--output', default='/tmp/target_environment_acceptance.json')
    parser.add_argument('--quality-manifest', default='/tmp/release_quality_manifest.json')
    parser.add_argument('--history-latest', default='/tmp/release_quality_history/latest.json')
    parser.add_argument('--evidence-report', default='/tmp/evidence_report.json')
    parser.add_argument('--acceptance-report', default='/tmp/acceptance_report.json')
    parser.add_argument('--host-harness-report', default='/tmp/host_harness_acceptance.json')
    parser.add_argument('--real-board-report', default='/tmp/real_board_acceptance.json')
    parser.add_argument('--hardware-in-loop-report', default='')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--profile-name', default='target_acceptance')
    parser.add_argument('--require-live-runtime', action='store_true', help='Fail when ros2/rclpy are unavailable.')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    ros2_info = _command_output('ros2', '--version')
    node_info = _command_output('node', '--version')
    npm_info = _command_output('npm', '--version')
    colcon_info = _command_output('colcon', '--version')
    rclpy_available = importlib.util.find_spec('rclpy') is not None

    if args.require_live_runtime and (not ros2_info['available'] or not rclpy_available):
        missing = []
        if not ros2_info['available']:
            missing.append('ros2')
        if not rclpy_available:
            missing.append('rclpy')
        raise SystemExit(f'missing live ROS runtime dependencies: {", ".join(missing)}')

    host_harness_artifact = describe_file(args.host_harness_report)
    real_board_artifact = describe_file(args.real_board_report)
    hardware_in_loop_artifact = describe_file(args.hardware_in_loop_report) if str(args.hardware_in_loop_report).strip() else {'path': '', 'exists': False, 'isFile': False, 'sizeBytes': None, 'modifiedAtUtc': None, 'sha256': None}

    host_payload = _load_json_file(args.host_harness_report)
    real_payload = _load_json_file(args.real_board_report)
    hil_payload = _load_json_file(args.hardware_in_loop_report) if str(args.hardware_in_loop_report).strip() else {}

    host_validation = validate_acceptance_artifact(host_payload, expected_type='host_harness_acceptance', require_hardware_identity=False, require_firmware_identity=False)
    real_validation = validate_acceptance_artifact(real_payload, expected_type='real_board_acceptance', require_hardware_identity=True, require_firmware_identity=False)
    hil_validation = validate_acceptance_artifact(hil_payload, expected_type='hardware_in_loop_acceptance', require_hardware_identity=True, require_firmware_identity=True) if hil_payload else None

    identity_reference = build_verification_identity(repo_root=Path(__file__).resolve().parents[1], config_path=args.config_path, profile_name=args.profile_name, hardware_identity={}, firmware_identity={})
    identity_match_ok, identity_errors = acceptance_identity_match(*(item.normalized for item in (host_validation, real_validation) if item.valid))
    host_reference_ok, host_reference_errors = acceptance_identity_matches_reference(
        host_validation.normalized,
        reference_identity=identity_reference,
        require_hardware_identity=False,
        require_firmware_identity=False,
    ) if host_validation.valid else (False, [])
    host_harness_observed = host_validation.valid and host_reference_ok
    identity_errors.extend(host_reference_errors)

    real_reference_identity = build_verification_identity(
        repo_root=Path(__file__).resolve().parents[1],
        config_path=args.config_path,
        profile_name=args.profile_name,
        hardware_identity=real_validation.normalized.get('verificationIdentity', {}).get('hardwareIdentity', {}) if real_validation.valid else {},
        firmware_identity={},
    )
    real_reference_ok, real_reference_errors = acceptance_identity_matches_reference(
        real_validation.normalized,
        reference_identity=real_reference_identity,
        require_hardware_identity=True,
        require_firmware_identity=False,
    ) if real_validation.valid else (False, [])
    identity_errors.extend(real_reference_errors)
    real_board_observed = real_validation.valid and identity_match_ok and real_reference_ok

    hardware_in_loop_verified = bool(hil_validation and hil_validation.valid)
    if hardware_in_loop_verified:
        accepted, hil_identity_errors = acceptance_identity_match(real_validation.normalized, hil_validation.normalized)
        hil_reference_identity = build_verification_identity(
            repo_root=Path(__file__).resolve().parents[1],
            config_path=args.config_path,
            profile_name=args.profile_name,
            hardware_identity=hil_validation.normalized.get('verificationIdentity', {}).get('hardwareIdentity', {}),
            firmware_identity=hil_validation.normalized.get('verificationIdentity', {}).get('firmwareIdentity', {}),
        )
        hil_reference_ok, hil_reference_errors = acceptance_identity_matches_reference(
            hil_validation.normalized,
            reference_identity=hil_reference_identity,
            require_hardware_identity=True,
            require_firmware_identity=True,
        )
        hardware_in_loop_verified = accepted and not hil_identity_errors and hil_reference_ok
        identity_errors.extend(hil_identity_errors)
        identity_errors.extend(hil_reference_errors)

    coverage_status = _coverage_status(
        ros2_available=bool(ros2_info['available']),
        rclpy_available=rclpy_available,
        host_harness_valid=host_harness_observed,
        real_board_valid=real_board_observed,
        hardware_in_loop_valid=hardware_in_loop_verified,
    )
    overall_status = coverage_status

    payload = {
        'schemaVersion': ACCEPTANCE_SCHEMA_VERSION,
        'artifactType': 'target_environment_acceptance',
        'capturedAtUtc': datetime.now(timezone.utc).isoformat(),
        'host': {
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'pythonVersion': sys.version.split()[0],
            'osRelease': _read_os_release(),
        },
        'runtime': {
            'ros2': ros2_info,
            'rclpyAvailable': rclpy_available,
            'node': node_info,
            'npm': npm_info,
            'colcon': colcon_info,
        },
        'verificationIdentity': identity_reference,
        'artifacts': {
            'releaseQualityManifest': describe_file(args.quality_manifest),
            'releaseQualityHistoryLatest': describe_file(args.history_latest),
            'evidenceReport': describe_file(args.evidence_report),
            'acceptanceReport': describe_file(args.acceptance_report),
            'hostHarnessAcceptance': host_harness_artifact,
            'realBoardAcceptance': real_board_artifact,
            'hardwareInLoopAcceptance': hardware_in_loop_artifact,
        },
        'verificationCoverage': {
            'hostHarnessObserved': host_harness_observed,
            'realBoardObserved': real_board_observed,
            'hardwareInLoopVerified': hardware_in_loop_verified,
            'hardwareInLoopArtifactPresent': bool(hardware_in_loop_artifact['exists']),
            'hostHarnessVerified': host_harness_observed,
            'realBoardVerified': hardware_in_loop_verified,
            'legacyRealBoardObservedAlias': real_board_observed,
            'hostHarnessArtifactPresent': bool(host_harness_artifact['exists']),
            'realBoardArtifactPresent': bool(real_board_artifact['exists']),
            'status': coverage_status,
            'hostHarnessEvidenceClass': evidence_class_payload('integration_live_ros_mock_robot'),
            'realBoardEvidenceClass': evidence_class_payload('hardware_probe_observational'),
            'hardwareInLoopEvidenceClass': evidence_class_payload('hardware_in_loop'),
            'claimBoundary': _claim_boundary(
                host_harness_valid=host_harness_observed,
                real_board_valid=real_board_observed,
                hardware_in_loop_valid=hardware_in_loop_verified,
            ),
            'validationErrors': {
                'hostHarness': list(host_validation.errors),
                'realBoard': list(real_validation.errors),
                'hardwareInLoop': list(hil_validation.errors) if hil_validation is not None else [],
                'identity': identity_errors,
            },
        },
        'status': overall_status,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
