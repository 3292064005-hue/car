#!/usr/bin/env python3
"""Capture target-environment acceptance evidence for a completed release verification run.

The report produced by this script is intended to accompany a live ROS 2 Humble
verification run executed on the target delivery environment. It records host and
runtime metadata together with the key verification artifacts produced by
``run_release_verification.sh``.
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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_utils.verification_evidence import evidence_class_payload


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


def _artifact_entry(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    return {
        'path': str(path),
        'exists': path.exists(),
        'sizeBytes': path.stat().st_size if path.exists() and path.is_file() else None,
    }


def _load_json_file(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _artifact_passed(path_value: str) -> bool:
    payload = _load_json_file(path_value)
    return bool(payload.get('passed', False))


def _coverage_status(*, ros2_available: bool, rclpy_available: bool, host_harness_passed: bool, real_board_passed: bool) -> str:
    if ros2_available and rclpy_available and host_harness_passed and real_board_passed:
        return 'ready_host_harness_plus_hardware_probe'
    if ros2_available and rclpy_available and real_board_passed:
        return 'ready_hardware_probe_only'
    if ros2_available and rclpy_available and host_harness_passed:
        return 'ready_host_harness_only'
    if ros2_available and rclpy_available:
        return 'ready_runtime_evidence_incomplete'
    return 'incomplete_runtime'


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Capture target environment acceptance evidence.')
    parser.add_argument('--output', default='/tmp/target_environment_acceptance.json')
    parser.add_argument('--quality-manifest', default='/tmp/release_quality_manifest.json')
    parser.add_argument('--history-latest', default='/tmp/release_quality_history/latest.json')
    parser.add_argument('--evidence-report', default='/tmp/evidence_report.json')
    parser.add_argument('--acceptance-report', default='/tmp/acceptance_report.json')
    parser.add_argument('--host-harness-report', default='/tmp/host_harness_acceptance.json')
    parser.add_argument('--real-board-report', default='/tmp/real_board_acceptance.json')
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

    host_harness_artifact = _artifact_entry(args.host_harness_report)
    real_board_artifact = _artifact_entry(args.real_board_report)
    host_harness_passed = _artifact_passed(args.host_harness_report)
    real_board_passed = _artifact_passed(args.real_board_report)
    coverage_status = _coverage_status(
        ros2_available=bool(ros2_info['available']),
        rclpy_available=rclpy_available,
        host_harness_passed=host_harness_passed,
        real_board_passed=real_board_passed,
    )

    if coverage_status == 'ready_host_harness_plus_hardware_probe':
        overall_status = 'ready_host_harness_plus_hardware_probe'
    elif coverage_status == 'ready_hardware_probe_only':
        overall_status = 'ready_hardware_probe_only'
    elif coverage_status == 'ready_host_harness_only':
        overall_status = 'ready_host_harness_only'
    elif coverage_status == 'ready_runtime_evidence_incomplete':
        overall_status = 'ready_runtime_evidence_incomplete'
    else:
        overall_status = 'incomplete_runtime'

    payload = {
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
        'artifacts': {
            'releaseQualityManifest': _artifact_entry(args.quality_manifest),
            'releaseQualityHistoryLatest': _artifact_entry(args.history_latest),
            'evidenceReport': _artifact_entry(args.evidence_report),
            'acceptanceReport': _artifact_entry(args.acceptance_report),
            'hostHarnessAcceptance': host_harness_artifact,
            'realBoardAcceptance': real_board_artifact,
        },
        'verificationCoverage': {
            'hostHarnessVerified': host_harness_passed,
            'realBoardVerified': real_board_passed,
            'hostHarnessArtifactPresent': bool(host_harness_artifact['exists']),
            'realBoardArtifactPresent': bool(real_board_artifact['exists']),
            'status': coverage_status,
            'hostHarnessEvidenceClass': evidence_class_payload('integration_live_ros_mock_robot'),
            'realBoardEvidenceClass': evidence_class_payload('hardware_probe_observational'),
        },
        'status': overall_status,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
