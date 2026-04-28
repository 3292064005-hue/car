#!/usr/bin/env python3
from __future__ import annotations

"""Bind the committed hardware-in-loop acceptance artifact to real HIL input.

This script is deliberately not a HIL-success generator. It derives the runtime
activation artifact from an existing HIL run report and fails closed when that
report is missing, incomplete, failed, stale, or inconsistent with the current
source/config/protocol identity.

The HIL report is expected to contain the identity captured when the HIL run was
executed. This script compares that execution identity against the current
repository identity; it must not replace missing execution identity with the
current one.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir() and str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))

from robot_utils.acceptance_bundle import (  # noqa: E402
    ACCEPTANCE_SCHEMA_VERSION,
    build_verification_identity,
)
from robot_utils.verification_evidence import evidence_class_payload  # noqa: E402

DEFAULT_OUTPUT = ROOT / 'ros2_ws' / 'src' / 'robot_bringup' / 'config' / 'hardware_in_loop_acceptance.json'
DEFAULT_CONFIG_PATH = ROOT / 'ros2_ws' / 'src' / 'robot_bringup' / 'config'
DEFAULT_PROFILE = 'hardware'
DEFAULT_INPUT_REPORT = ROOT / 'artifacts' / 'hardware_in_loop' / 'hil_execution_report.json'
_SHA256_RE = re.compile(r'^[0-9a-fA-F]{64}$')


class HilReportError(ValueError):
    """Raised when HIL source evidence is missing or not trustworthy enough."""


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _resolve_repo_path(path_value: str) -> Path:
    path = Path(str(path_value or '').strip())
    if not str(path):
        raise HilReportError('empty artifact path')
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise HilReportError(f'HIL input report is missing: {path}')
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise HilReportError(f'HIL input report is not valid JSON: {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise HilReportError('HIL input report must be a JSON object')
    return payload


def _mapping(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    return dict(value) if isinstance(value, Mapping) else {}


def _require_string(payload: Mapping[str, Any], key: str) -> str:
    value = str(payload.get(key, '') or '').strip()
    if not value:
        raise HilReportError(f'HIL input report missing required field: {key}')
    return value


def _require_bool(payload: Mapping[str, Any], key: str) -> bool:
    if payload.get(key) is not True:
        raise HilReportError(f'HIL input report field must be true: {key}')
    return True


def _same_json(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True, separators=(',', ':')) == json.dumps(right, sort_keys=True, separators=(',', ':'))


def _require_dict_equal(*, name: str, report_value: Mapping[str, Any], reference_value: Mapping[str, Any]) -> None:
    if not _same_json(dict(report_value), dict(reference_value)):
        raise HilReportError(f'HIL input report execution identity mismatch: {name}')


def _validate_raw_evidence(raw: Mapping[str, Any]) -> dict[str, str]:
    required = {
        'commandTranscriptPath': 'commandTranscriptSha256',
        'telemetryTranscriptPath': 'telemetryTranscriptSha256',
        'heartbeatTranscriptPath': 'heartbeatTranscriptSha256',
        'safetyEventLogPath': 'safetyEventLogSha256',
    }
    normalized: dict[str, str] = {}
    for path_key, sha_key in required.items():
        rel_path = _require_string(raw, path_key)
        expected_sha = _require_string(raw, sha_key).lower()
        if not _SHA256_RE.match(expected_sha):
            raise HilReportError(f'rawEvidence.{sha_key} must be a 64-character sha256 hex digest')
        path = _resolve_repo_path(rel_path)
        if not path.is_file():
            raise HilReportError(f'raw evidence file is missing: {rel_path}')
        actual_sha = _sha256_file(path).lower()
        if actual_sha != expected_sha:
            raise HilReportError(f'raw evidence sha256 mismatch: {rel_path}')
        if path.stat().st_size <= 0:
            raise HilReportError(f'raw evidence file is empty: {rel_path}')
        normalized[path_key] = _repo_relative(path)
        normalized[sha_key] = expected_sha
    return normalized


def _validate_report(
    payload: Mapping[str, Any],
    *,
    report_path: Path,
    reference_identity: Mapping[str, Any],
) -> dict[str, Any]:
    if int(payload.get('schemaVersion', 0) or 0) != 2:
        raise HilReportError('HIL input report schemaVersion must be 2')
    if str(payload.get('artifactType', '') or '') != 'hardware_in_loop_run_report':
        raise HilReportError('HIL input report artifactType must be hardware_in_loop_run_report')
    _require_bool(payload, 'passed')
    run_id = _require_string(payload, 'runId')
    captured_at = _require_string(payload, 'capturedAtUtc')
    test_environment = _require_string(payload, 'testEnvironment')

    report_identity = _mapping(payload, 'verificationIdentity')
    if not report_identity:
        raise HilReportError('HIL input report missing required field: verificationIdentity')
    for key in ('profileName', 'configRoot', 'launchProfilesPath', 'configDigest', 'protocolIdentity', 'sourceReleaseIdentity'):
        if key not in report_identity:
            raise HilReportError(f'HIL input report verificationIdentity missing required field: {key}')
    for key in ('profileName', 'configRoot', 'launchProfilesPath', 'configDigest'):
        if str(report_identity.get(key, '') or '') != str(reference_identity.get(key, '') or ''):
            raise HilReportError(f'HIL input report execution identity mismatch: {key}')
    _require_dict_equal(
        name='sourceReleaseIdentity',
        report_value=_mapping(report_identity, 'sourceReleaseIdentity'),
        reference_value=_mapping(reference_identity, 'sourceReleaseIdentity'),
    )
    _require_dict_equal(
        name='protocolIdentity',
        report_value=_mapping(report_identity, 'protocolIdentity'),
        reference_value=_mapping(reference_identity, 'protocolIdentity'),
    )

    hardware = _mapping(payload, 'hardwareIdentity')
    board_id = _require_string(hardware, 'boardId')
    board_class = _require_string(hardware, 'boardClass')
    _require_dict_equal(
        name='hardwareIdentity',
        report_value=hardware,
        reference_value=_mapping(report_identity, 'hardwareIdentity'),
    )

    firmware = _mapping(payload, 'firmwareIdentity')
    firmware_version = _require_string(firmware, 'firmwareVersion')
    firmware_sha256 = _require_string(firmware, 'firmwareSha256').lower()
    if not _SHA256_RE.match(firmware_sha256):
        raise HilReportError('firmwareIdentity.firmwareSha256 must be a 64-character sha256 hex digest')
    firmware_artifact_path = str(firmware.get('firmwareArtifactPath', '') or '').strip()
    if firmware_artifact_path:
        fw_path = _resolve_repo_path(firmware_artifact_path)
        if not fw_path.is_file():
            raise HilReportError(f'firmware artifact path is missing: {firmware_artifact_path}')
        actual_sha = _sha256_file(fw_path)
        if actual_sha.lower() != firmware_sha256:
            raise HilReportError('firmwareIdentity.firmwareSha256 does not match firmwareArtifactPath')
    _require_dict_equal(
        name='firmwareIdentity',
        report_value=firmware,
        reference_value=_mapping(report_identity, 'firmwareIdentity'),
    )

    runtime = _mapping(payload, 'runtime')
    ros2 = _mapping(runtime, 'ros2')
    if ros2.get('available') is not True:
        raise HilReportError('runtime.ros2.available must be true in HIL input report')
    if runtime.get('rclpyAvailable') is not True:
        raise HilReportError('runtime.rclpyAvailable must be true in HIL input report')
    runtime_identity = _mapping(runtime, 'runtimeIdentity')
    for key in ('directDriverPackage', 'directDriverExecutable', 'transportProtocol', 'protocolVersion'):
        _require_string(runtime_identity, key)

    coverage = _mapping(payload, 'verificationCoverage')
    for key in ('hostHarnessVerified', 'realBoardObserved', 'hardwareInLoopVerified'):
        if coverage.get(key) is not True:
            raise HilReportError(f'verificationCoverage.{key} must be true in HIL input report')

    observations = _mapping(payload, 'observations')
    for key in ('commandCycles', 'telemetrySamples'):
        try:
            if int(observations.get(key, 0) or 0) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise HilReportError(f'observations.{key} must be a positive integer')
    for key in (
        'heartbeatObserved',
        'safetyStopTested',
        'cmdVelToBoardAckObserved',
        'wheelTelemetryObserved',
        'faultClearRoundTripObserved',
    ):
        if observations.get(key) is not True:
            raise HilReportError(f'observations.{key} must be true')

    raw_evidence = _validate_raw_evidence(_mapping(payload, 'rawEvidence'))
    test_runner_identity = _mapping(payload, 'testRunnerIdentity')
    for key in ('name', 'version', 'runnerSha256'):
        _require_string(test_runner_identity, key)
    if not _SHA256_RE.match(str(test_runner_identity.get('runnerSha256', '') or '').lower()):
        raise HilReportError('testRunnerIdentity.runnerSha256 must be a 64-character sha256 hex digest')

    return {
        'runId': run_id,
        'capturedAtUtc': captured_at,
        'testEnvironment': test_environment,
        'operator': str(payload.get('operator', '') or '').strip(),
        'hardwareIdentity': {'boardId': board_id, 'boardClass': board_class},
        'firmwareIdentity': {
            'firmwareVersion': firmware_version,
            'firmwareSha256': firmware_sha256,
            **({'firmwareArtifactPath': firmware_artifact_path} if firmware_artifact_path else {}),
        },
        'runtime': runtime,
        'runtimeIdentity': runtime_identity,
        'verificationIdentity': dict(report_identity),
        'verificationCoverage': coverage,
        'observations': observations,
        'rawEvidence': raw_evidence,
        'testRunnerIdentity': dict(test_runner_identity),
        'sourceEvidence': {
            'sourceArtifactType': 'hardware_in_loop_run_report',
            'sourceArtifactPath': _repo_relative(report_path),
            'sourceArtifactSha256': _sha256_file(report_path),
            'runId': run_id,
            'capturedAtUtc': captured_at,
            'testEnvironment': test_environment,
        },
    }


def build_payload(*, repo_root: Path, config_path: str, profile_name: str, input_report: Path) -> dict[str, object]:
    reference_identity = build_verification_identity(
        repo_root=repo_root,
        config_path=config_path,
        profile_name=profile_name,
        hardware_identity={},
        firmware_identity={},
    )
    report_payload = _read_json_mapping(input_report)
    # The source report must carry the execution-time hardware/firmware identity.
    # Rebuild the reference identity with those identities only for exact compare.
    report_hardware = _mapping(report_payload, 'hardwareIdentity')
    report_firmware = _mapping(report_payload, 'firmwareIdentity')
    reference_identity = build_verification_identity(
        repo_root=repo_root,
        config_path=config_path,
        profile_name=profile_name,
        hardware_identity=report_hardware,
        firmware_identity=report_firmware,
    )
    report = _validate_report(report_payload, report_path=input_report, reference_identity=reference_identity)
    evidence_class = evidence_class_payload('hardware_in_loop')
    return {
        'schemaVersion': ACCEPTANCE_SCHEMA_VERSION,
        'artifactType': 'hardware_in_loop_acceptance',
        'capturedAtUtc': datetime.now(timezone.utc).isoformat(),
        'status': 'target_environment_accepted_via_hil',
        'passed': True,
        'evidenceClass': evidence_class,
        'runtime': report['runtime'],
        # Do not synthesize identity. This is copied from the HIL execution
        # report after exact matching against the current source/config/protocol
        # reference identity.
        'verificationIdentity': report['verificationIdentity'],
        'verificationCoverage': report['verificationCoverage'],
        'claimBoundary': list(evidence_class['supportedClaims']),
        'sourceEvidence': report['sourceEvidence'],
        'resultSummary': {
            'activationEvidence': 'operator_supplied_hardware_in_loop_run_report',
            'activationProfiles': ['hardware', 'full', 'demo'],
            'mockProfilesDowngradeTo': 'ros_projection_only',
            'observations': report['observations'],
            'rawEvidence': report['rawEvidence'],
            'testRunnerIdentity': report['testRunnerIdentity'],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Bind committed hardware-in-loop acceptance artifact to HIL run evidence')
    parser.add_argument('--input-report', default=str(DEFAULT_INPUT_REPORT), help='Existing HIL execution report; required and must pass provenance checks')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    parser.add_argument('--config-path', default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument('--profile-name', default=DEFAULT_PROFILE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    input_report = Path(args.input_report)
    payload = build_payload(
        repo_root=ROOT,
        config_path=str(args.config_path),
        profile_name=str(args.profile_name),
        input_report=input_report,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': 'ok',
        'output': str(output),
        'inputReport': str(input_report),
        'sourceEvidenceSha256': payload['sourceEvidence']['sourceArtifactSha256'],
        'artifactId': payload['verificationIdentity']['sourceReleaseIdentity']['artifactId'],
        'sourceTreeSha256': payload['verificationIdentity']['sourceReleaseIdentity']['sourceTreeSha256'],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    import os
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(code))
