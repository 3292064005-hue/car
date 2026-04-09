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


def config_digest(config_path: str | Path | None = None) -> str:
    resolved = resolve_bringup_config(str(config_path) if config_path else None)
    files = sorted(
        path for path in resolved.config_root.rglob('*')
        if path.is_file() and path.suffix.lower() in {'.yaml', '.yml', '.json'}
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(resolved.config_root)).encode('utf-8'))
        digest.update(b'\\0')
        digest.update(path.read_bytes())
        digest.update(b'\\0')
    return digest.hexdigest()


def source_release_identity(repo_root: str | Path) -> dict[str, Any]:
    repo = Path(repo_root)
    manifest_path = repo / 'workspace_manifest.json'
    return {
        'workspaceManifestPath': str(manifest_path),
        'workspaceManifestSha256': _sha256_path(manifest_path) if manifest_path.is_file() else '',
    }


def protocol_identity(repo_root: str | Path) -> dict[str, Any]:
    repo = Path(repo_root)
    tcp_doc = repo / 'docs/04_tcp_json_protocol.md'
    uart_doc = repo / 'docs/05_uart_binary_protocol.md'
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
    return {
        'profileName': str(profile_name or 'target_acceptance'),
        'configRoot': str(resolved.config_root),
        'launchProfilesPath': str(resolved.launch_profiles_path),
        'configDigest': config_digest(config_path),
        'protocolIdentity': protocol_identity(repo_root),
        'sourceReleaseIdentity': source_release_identity(repo_root),
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
    errors.extend(f'source_release_identity.{key}_missing' for key in _required_keys(source_release, ('workspaceManifestPath', 'workspaceManifestSha256')))
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
