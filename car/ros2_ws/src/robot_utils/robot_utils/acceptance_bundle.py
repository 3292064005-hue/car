from __future__ import annotations

"""Helpers for acceptance evidence identity, schema, and provenance checks.

The target-environment acceptance gate must not trust arbitrary JSON payloads
that merely say ``passed=true``. This module centralizes the stronger schema and
identity checks shared by acceptance capture, evidence reporting, and tests.
"""

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping

from robot_bringup.config_resolution import resolve_bringup_config
from robot_contracts.bridge_contract import PROTOCOL_VERSION, TCP_PROTOCOL_VERSION, UART_PROTOCOL_VERSION, SCHEMA_VERSION
from robot_utils.repository_identity import repository_identity

ACCEPTANCE_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]
    normalized: dict[str, Any]


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_text_parts(parts: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part).encode('utf-8'))
        digest.update(b'\\0')
    return digest.hexdigest()


def _repo_relative_path(path: Path, *, repo_root: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return None


def _acceptance_identity_exclude_rel_paths(*, repo_root: str | Path, config_path: str | Path | None = None) -> tuple[str, ...]:
    """Return repository-relative files excluded from acceptance source identity.

    Acceptance artifacts committed under the config root are runtime evidence,
    not part of the declarative source/config surface they attest to. Keeping
    them inside the source-tree hash would make committed artifacts
    self-invalidating as soon as they are refreshed.
    """
    repo = Path(repo_root).resolve()
    exclude: set[str] = {'artifacts/validation/VALIDATION_EVIDENCE.md'}
    # HIL evidence artifacts describe an execution against the source tree; they
    # are not themselves part of the code/config/protocol surface being attested.
    # Including them would make the HIL report self-referential and unstable as
    # soon as the report is refreshed.
    hil_dir = repo / 'artifacts' / 'hardware_in_loop'
    if hil_dir.is_dir():
        for path in sorted(hil_dir.rglob('*')):
            if not path.is_file():
                continue
            rel = _repo_relative_path(path, repo_root=repo)
            if rel:
                exclude.add(rel)
    resolved = resolve_bringup_config(str(config_path) if config_path else None)
    for path in sorted(resolved.config_root.glob('*acceptance*.json')):
        if not path.is_file():
            continue
        rel = _repo_relative_path(path, repo_root=repo)
        if rel:
            exclude.add(rel)
    return tuple(sorted(exclude))


def _portable_repo_path(path: Path, *, repo_root: Path) -> str:
    rel = _repo_relative_path(path, repo_root=repo_root)
    return rel if rel is not None else str(path.resolve())


def config_digest(config_path: str | Path | None = None) -> str:
    """Hash the declarative bringup configuration surface.

    Generated JSON evidence files may live beside the YAML config tree. They are
    not part of the declarative runtime configuration and must not be folded
    into the identity digest, otherwise acceptance artifacts become
    self-invalidating as soon as they are written.
    """
    resolved = resolve_bringup_config(str(config_path) if config_path else None)
    files = sorted(
        path for path in resolved.config_root.rglob('*')
        if path.is_file() and path.suffix.lower() in {'.yaml', '.yml'}
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(resolved.config_root)).encode('utf-8'))
        digest.update(b'\\0')
        digest.update(path.read_bytes())
        digest.update(b'\\0')
    return digest.hexdigest()


def source_release_identity(repo_root: str | Path, *, config_path: str | Path | None = None) -> dict[str, Any]:
    repo = Path(repo_root)
    identity = repository_identity(repo, exclude_rel_paths=_acceptance_identity_exclude_rel_paths(repo_root=repo, config_path=config_path))
    return {
        'workspaceManifestPath': _portable_repo_path(Path(identity['workspaceManifestPath']), repo_root=repo.resolve()),
        'workspaceManifestSha256': identity['workspaceManifestSha256'],
        'workspaceId': identity['workspaceId'],
        'artifactId': identity['artifactId'],
        'sourceTreeSha256': identity['sourceTreeSha256'],
        'layoutMode': identity['layoutMode'],
        'includedFileCount': identity['includedFileCount'],
    }


def protocol_identity(repo_root: str | Path) -> dict[str, Any]:
    repo = Path(repo_root)
    tcp_doc = repo / 'docs/protocols/tcp-json.md'
    uart_doc = repo / 'docs/protocols/uart-binary.md'
    return {
        'webProtocolVersion': PROTOCOL_VERSION,
        'schemaVersion': SCHEMA_VERSION,
        'tcpProtocolVersion': TCP_PROTOCOL_VERSION,
        'uartProtocolVersion': UART_PROTOCOL_VERSION,
        'tcpProtocolDocSha256': _sha256_path(tcp_doc) if tcp_doc.is_file() else '',
        'uartProtocolDocSha256': _sha256_path(uart_doc) if uart_doc.is_file() else '',
    }


def build_verification_identity(
    *,
    repo_root: str | Path,
    config_path: str | Path | None,
    profile_name: str,
    hardware_identity: Mapping[str, Any] | None = None,
    firmware_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = resolve_bringup_config(str(config_path) if config_path else None)
    hardware = {k: v for k, v in dict(hardware_identity or {}).items() if v not in (None, '', [], {})}
    firmware = {k: v for k, v in dict(firmware_identity or {}).items() if v not in (None, '', [], {})}
    repo = Path(repo_root).resolve()
    return {
        'profileName': str(profile_name or 'target_acceptance'),
        'configRoot': _portable_repo_path(resolved.config_root, repo_root=repo),
        'launchProfilesPath': _portable_repo_path(resolved.launch_profiles_path, repo_root=repo),
        'configDigest': config_digest(config_path),
        'protocolIdentity': protocol_identity(repo_root),
        'sourceReleaseIdentity': source_release_identity(repo_root, config_path=config_path),
        'hardwareIdentity': hardware,
        'firmwareIdentity': firmware,
    }


def _required_keys(mapping: Mapping[str, Any], keys: Iterable[str]) -> list[str]:
    return [key for key in keys if mapping.get(key) in (None, '', [], {})]


def validate_acceptance_artifact(
    payload: Mapping[str, Any] | None,
    *,
    expected_type: str,
    require_hardware_identity: bool,
    require_firmware_identity: bool,
) -> ValidationResult:
    errors: list[str] = []
    normalized = dict(payload or {}) if isinstance(payload, Mapping) else {}
    if not normalized:
        return ValidationResult(False, ('artifact_missing_or_not_mapping',), {})
    if int(normalized.get('schemaVersion', 0) or 0) != ACCEPTANCE_SCHEMA_VERSION:
        errors.append('schema_version_mismatch')
    if str(normalized.get('artifactType', '') or '') != expected_type:
        errors.append('artifact_type_mismatch')
    if not bool(normalized.get('passed', False)):
        errors.append('artifact_not_passed')
    evidence_class = normalized.get('evidenceClass', {}) if isinstance(normalized.get('evidenceClass', {}), Mapping) else {}
    if not str(evidence_class.get('key', '') or ''):
        errors.append('evidence_class_missing')
    verification = normalized.get('verificationIdentity', {}) if isinstance(normalized.get('verificationIdentity', {}), Mapping) else {}
    errors.extend(f'verification_identity.{key}_missing' for key in _required_keys(verification, ('profileName', 'configRoot', 'launchProfilesPath', 'configDigest')))
    protocol = verification.get('protocolIdentity', {}) if isinstance(verification.get('protocolIdentity', {}), Mapping) else {}
    errors.extend(f'protocol_identity.{key}_missing' for key in _required_keys(protocol, ('webProtocolVersion', 'schemaVersion', 'tcpProtocolVersion', 'uartProtocolVersion', 'tcpProtocolDocSha256', 'uartProtocolDocSha256')))
    source_release = verification.get('sourceReleaseIdentity', {}) if isinstance(verification.get('sourceReleaseIdentity', {}), Mapping) else {}
    errors.extend(f'source_release_identity.{key}_missing' for key in _required_keys(source_release, ('workspaceManifestPath', 'workspaceManifestSha256', 'workspaceId', 'artifactId', 'sourceTreeSha256', 'layoutMode')))
    if require_hardware_identity:
        hardware = verification.get('hardwareIdentity', {}) if isinstance(verification.get('hardwareIdentity', {}), Mapping) else {}
        errors.extend(f'hardware_identity.{key}_missing' for key in _required_keys(hardware, ('boardId', 'boardClass')))
    if require_firmware_identity:
        firmware = verification.get('firmwareIdentity', {}) if isinstance(verification.get('firmwareIdentity', {}), Mapping) else {}
        # Require at least a version-ish field and a content hash.
        if firmware.get('firmwareVersion') in (None, ''):
            errors.append('firmware_identity.firmwareVersion_missing')
        if firmware.get('firmwareSha256') in (None, ''):
            errors.append('firmware_identity.firmwareSha256_missing')
    return ValidationResult(len(errors) == 0, tuple(errors), normalized)



def validate_target_environment_acceptance(
    payload: Mapping[str, Any] | None,
    *,
    repo_root: str | Path,
    config_path: str | Path | None = None,
) -> ValidationResult:
    """Validate a target-environment acceptance artifact against final-delivery rules.

    The target-environment artifact is the strongest repository-local evidence for
    direct board-execution claims. Runtime boundary reports and final delivery
    gates must therefore share the same validation logic instead of maintaining
    separate weak/strong schema branches.

    Args:
        payload: Candidate artifact mapping.
        repo_root: Repository root used to compute the reference identity.
        config_path: Optional config root override used when building the
            reference verification identity.

    Returns:
        Validation result containing the normalized payload and any validation
        errors that block target-environment acceptance claims.
    """
    base = validate_acceptance_artifact(
        payload,
        expected_type='target_environment_acceptance',
        require_hardware_identity=False,
        require_firmware_identity=False,
    )
    if not base.valid:
        return base

    normalized = dict(base.normalized)
    errors = list(base.errors)
    verification = normalized.get('verificationIdentity', {}) if isinstance(normalized.get('verificationIdentity', {}), Mapping) else {}
    reference_identity = build_verification_identity(
        repo_root=repo_root,
        config_path=config_path,
        profile_name=str(verification.get('profileName', '') or 'target_acceptance'),
        hardware_identity={},
        firmware_identity={},
    )
    reference_ok, reference_errors = acceptance_identity_matches_reference(
        normalized,
        reference_identity=reference_identity,
        require_hardware_identity=False,
        require_firmware_identity=False,
    )
    if not reference_ok:
        errors.extend(reference_errors)

    evidence_class = normalized.get('evidenceClass', {}) if isinstance(normalized.get('evidenceClass', {}), Mapping) else {}
    if str(evidence_class.get('key', '') or '') != 'hardware_in_loop':
        errors.append('target_environment_evidence_class_not_hardware_in_loop')

    runtime = normalized.get('runtime', {}) if isinstance(normalized.get('runtime', {}), Mapping) else {}
    ros2_info = runtime.get('ros2', {}) if isinstance(runtime.get('ros2', {}), Mapping) else {}
    verification_coverage = normalized.get('verificationCoverage', {}) if isinstance(normalized.get('verificationCoverage', {}), Mapping) else {}
    if str(normalized.get('status', '') or '') != 'target_environment_accepted':
        errors.append('target_environment_status_not_accepted')
    if not bool(verification_coverage.get('hostHarnessVerified', False)):
        errors.append('target_environment_host_harness_not_verified')
    if not bool(verification_coverage.get('realBoardObserved', False)):
        errors.append('target_environment_real_board_not_observed')
    if not bool(verification_coverage.get('hardwareInLoopVerified', False)):
        errors.append('target_environment_hardware_in_loop_not_verified')
    if not bool(runtime.get('rclpyAvailable', False)):
        errors.append('target_environment_rclpy_unavailable')
    if not bool(ros2_info.get('available', False)):
        errors.append('target_environment_ros2_unavailable')

    return ValidationResult(len(errors) == 0, tuple(errors), normalized)


def acceptance_identity_match(*artifacts: Mapping[str, Any]) -> tuple[bool, list[str]]:
    identities = []
    for payload in artifacts:
        verification = payload.get('verificationIdentity', {}) if isinstance(payload.get('verificationIdentity', {}), Mapping) else {}
        identities.append(verification)
    errors: list[str] = []
    if not identities:
        return False, ['no_identities']
    reference = identities[0]
    ref_cfg = str(reference.get('configDigest', '') or '')
    ref_proto = reference.get('protocolIdentity', {}) if isinstance(reference.get('protocolIdentity', {}), Mapping) else {}
    ref_tcp_doc = str(ref_proto.get('tcpProtocolDocSha256', '') or '')
    ref_uart_doc = str(ref_proto.get('uartProtocolDocSha256', '') or '')
    ref_source = reference.get('sourceReleaseIdentity', {}) if isinstance(reference.get('sourceReleaseIdentity', {}), Mapping) else {}
    ref_manifest_sha = str(ref_source.get('workspaceManifestSha256', '') or '')
    ref_source_sha = str(ref_source.get('sourceTreeSha256', '') or '')
    for idx, identity in enumerate(identities[1:], start=1):
        if str(identity.get('configDigest', '') or '') != ref_cfg:
            errors.append(f'config_digest_mismatch:{idx}')
        proto = identity.get('protocolIdentity', {}) if isinstance(identity.get('protocolIdentity', {}), Mapping) else {}
        if str(proto.get('tcpProtocolDocSha256', '') or '') != ref_tcp_doc:
            errors.append(f'tcp_protocol_identity_mismatch:{idx}')
        if str(proto.get('uartProtocolDocSha256', '') or '') != ref_uart_doc:
            errors.append(f'uart_protocol_identity_mismatch:{idx}')
        source = identity.get('sourceReleaseIdentity', {}) if isinstance(identity.get('sourceReleaseIdentity', {}), Mapping) else {}
        if str(source.get('workspaceManifestSha256', '') or '') != ref_manifest_sha:
            errors.append(f'source_release_identity_mismatch:{idx}')
        if str(source.get('sourceTreeSha256', '') or '') != ref_source_sha:
            errors.append(f'source_tree_identity_mismatch:{idx}')
    return len(errors) == 0, errors


def acceptance_identity_matches_reference(
    artifact: Mapping[str, Any],
    *,
    reference_identity: Mapping[str, Any],
    require_hardware_identity: bool,
    require_firmware_identity: bool,
) -> tuple[bool, list[str]]:
    verification = artifact.get('verificationIdentity', {}) if isinstance(artifact.get('verificationIdentity', {}), Mapping) else {}
    errors: list[str] = []
    if str(verification.get('configDigest', '') or '') != str(reference_identity.get('configDigest', '') or ''):
        errors.append('config_digest_mismatch:reference')
    ref_proto = reference_identity.get('protocolIdentity', {}) if isinstance(reference_identity.get('protocolIdentity', {}), Mapping) else {}
    proto = verification.get('protocolIdentity', {}) if isinstance(verification.get('protocolIdentity', {}), Mapping) else {}
    if str(proto.get('tcpProtocolDocSha256', '') or '') != str(ref_proto.get('tcpProtocolDocSha256', '') or ''):
        errors.append('tcp_protocol_identity_mismatch:reference')
    if str(proto.get('uartProtocolDocSha256', '') or '') != str(ref_proto.get('uartProtocolDocSha256', '') or ''):
        errors.append('uart_protocol_identity_mismatch:reference')
    if str(proto.get('webProtocolVersion', '') or '') != str(ref_proto.get('webProtocolVersion', '') or ''):
        errors.append('web_protocol_identity_mismatch:reference')
    if str(proto.get('schemaVersion', '') or '') != str(ref_proto.get('schemaVersion', '') or ''):
        errors.append('schema_identity_mismatch:reference')
    if str(proto.get('tcpProtocolVersion', '') or '') != str(ref_proto.get('tcpProtocolVersion', '') or ''):
        errors.append('tcp_transport_identity_mismatch:reference')
    if str(proto.get('uartProtocolVersion', '') or '') != str(ref_proto.get('uartProtocolVersion', '') or ''):
        errors.append('uart_transport_identity_mismatch:reference')
    ref_source = reference_identity.get('sourceReleaseIdentity', {}) if isinstance(reference_identity.get('sourceReleaseIdentity', {}), Mapping) else {}
    source = verification.get('sourceReleaseIdentity', {}) if isinstance(verification.get('sourceReleaseIdentity', {}), Mapping) else {}
    if str(source.get('workspaceManifestSha256', '') or '') != str(ref_source.get('workspaceManifestSha256', '') or ''):
        errors.append('source_release_identity_mismatch:reference')
    if str(source.get('sourceTreeSha256', '') or '') != str(ref_source.get('sourceTreeSha256', '') or ''):
        errors.append('source_tree_identity_mismatch:reference')
    if str(source.get('layoutMode', '') or '') != str(ref_source.get('layoutMode', '') or ''):
        errors.append('source_release_layout_mismatch:reference')
    if require_hardware_identity:
        ref_hw = reference_identity.get('hardwareIdentity', {}) if isinstance(reference_identity.get('hardwareIdentity', {}), Mapping) else {}
        hw = verification.get('hardwareIdentity', {}) if isinstance(verification.get('hardwareIdentity', {}), Mapping) else {}
        if str(hw.get('boardId', '') or '') != str(ref_hw.get('boardId', '') or ''):
            errors.append('hardware_identity.boardId_mismatch:reference')
        if str(hw.get('boardClass', '') or '') != str(ref_hw.get('boardClass', '') or ''):
            errors.append('hardware_identity.boardClass_mismatch:reference')
    if require_firmware_identity:
        ref_fw = reference_identity.get('firmwareIdentity', {}) if isinstance(reference_identity.get('firmwareIdentity', {}), Mapping) else {}
        fw = verification.get('firmwareIdentity', {}) if isinstance(verification.get('firmwareIdentity', {}), Mapping) else {}
        if str(fw.get('firmwareVersion', '') or '') != str(ref_fw.get('firmwareVersion', '') or ''):
            errors.append('firmware_identity.firmwareVersion_mismatch:reference')
        if str(fw.get('firmwareSha256', '') or '') != str(ref_fw.get('firmwareSha256', '') or ''):
            errors.append('firmware_identity.firmwareSha256_mismatch:reference')
    return len(errors) == 0, errors
