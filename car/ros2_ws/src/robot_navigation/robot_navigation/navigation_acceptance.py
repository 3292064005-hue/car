from __future__ import annotations

"""Navigation acceptance artifact validation and gate resolution."""

from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from robot_utils.acceptance_bundle import validate_target_environment_acceptance

BASE_REQUIRED_NAV2_ARTIFACT_KEYS: tuple[str, ...] = (
    'simulation_smoke',
    'host_harness_smoke',
    'provider_switch_smoke',
    'operator_docs_review',
    'target_environment_acceptance',
)
OPTIONAL_NAV2_ARTIFACT_KEYS: tuple[str, ...] = ('external_backend_smoke',)

DEFAULT_NAV2_ARTIFACT_FILENAMES: dict[str, str] = {
    'simulation_smoke': 'nav2_simulation_smoke.json',
    'host_harness_smoke': 'host_harness_acceptance.json',
    'provider_switch_smoke': 'nav2_provider_switch_smoke.json',
    'operator_docs_review': 'nav2_operator_docs_review.json',
    'target_environment_acceptance': 'target_environment_acceptance.json',
    'external_backend_smoke': 'nav2_external_backend_smoke.json',
}

CONFIG_PARAM_TO_ARTIFACT_KEY: dict[str, str] = {
    'nav2_simulation_smoke_artifact_path': 'simulation_smoke',
    'nav2_host_harness_smoke_artifact_path': 'host_harness_smoke',
    'nav2_provider_switch_smoke_artifact_path': 'provider_switch_smoke',
    'nav2_operator_docs_review_artifact_path': 'operator_docs_review',
    'nav2_target_environment_acceptance_artifact_path': 'target_environment_acceptance',
    'nav2_external_backend_smoke_artifact_path': 'external_backend_smoke',
}

@dataclass(frozen=True)
class NavigationAcceptanceArtifact:
    artifact_key: str
    artifact_path: str
    artifact_type: str
    valid: bool
    errors: tuple[str, ...]
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {'artifactKey': self.artifact_key, 'artifactPath': self.artifact_path, 'artifactType': self.artifact_type, 'valid': self.valid, 'errors': list(self.errors), 'payload': self.payload}

@dataclass(frozen=True)
class NavigationAcceptanceGate:
    valid: bool
    artifacts: tuple[NavigationAcceptanceArtifact, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {'valid': self.valid, 'artifacts': [item.to_dict() for item in self.artifacts], 'errors': list(self.errors)}


def _resolve_relative_path(path_value: str | Path | None, *, reference_root: str | Path | None) -> str:
    normalized = str(path_value or '').strip()
    if not normalized:
        return ''
    candidate = Path(normalized)
    if candidate.is_absolute() or reference_root is None:
        return str(candidate)
    return str((Path(reference_root) / candidate).resolve())


def resolve_nav2_acceptance_artifact_paths(params: Mapping[str, Any] | None, *, config_root: str | Path | None, runtime_dir: str | Path | None) -> dict[str, str]:
    mapping = params if isinstance(params, Mapping) else {}
    runtime_root = Path(str(runtime_dir or '').strip() or '/tmp/inspection_robot')
    payload: dict[str, str] = {}
    for param_name, artifact_key in CONFIG_PARAM_TO_ARTIFACT_KEY.items():
        raw_value = str(mapping.get(param_name, '') or '').strip()
        if raw_value:
            payload[artifact_key] = _resolve_relative_path(raw_value, reference_root=config_root)
        else:
            config_candidate = (Path(config_root) / DEFAULT_NAV2_ARTIFACT_FILENAMES[artifact_key]).resolve() if config_root else None
            if config_candidate is not None and config_candidate.is_file():
                payload[artifact_key] = str(config_candidate)
            else:
                payload[artifact_key] = str((runtime_root / DEFAULT_NAV2_ARTIFACT_FILENAMES[artifact_key]).resolve())
    return payload


def nav2_external_backend_smoke_required(params: Mapping[str, Any] | None) -> bool:
    mapping = params if isinstance(params, Mapping) else {}
    backend_mode = str(mapping.get('backend_mode', 'auto') or 'auto').strip() or 'auto'
    stack_available = bool(mapping.get('external_nav2_stack_available', False))
    backend_integrated = bool(mapping.get('external_nav2_backend_integrated', False))
    return backend_integrated or (backend_mode == 'external_nav2_stack' and stack_available)


def _load_json_mapping(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _validate_smoke_artifact(payload: dict[str, Any], *, artifact_key: str, expected_types: tuple[str, ...], required_provider: str = 'nav2_provider') -> tuple[bool, tuple[str, ...], str]:
    errors: list[str] = []
    artifact_type = str(payload.get('artifactType', '') or '').strip()
    if artifact_type not in expected_types:
        errors.append(f'{artifact_key}_artifact_type_invalid')
    if not bool(payload.get('passed', False)):
        errors.append(f'{artifact_key}_not_passed')
    provider_name = str(payload.get('providerName', payload.get('provider', '')) or '').strip()
    if required_provider and provider_name != required_provider:
        errors.append(f'{artifact_key}_provider_mismatch')
    schema_version = int(payload.get('schemaVersion', 0) or 0)
    if schema_version < 1:
        errors.append(f'{artifact_key}_schema_too_old')
    return (not errors, tuple(errors), artifact_type)


def _validate_host_harness_artifact(payload: dict[str, Any]) -> tuple[bool, tuple[str, ...], str]:
    errors: list[str] = []
    artifact_type = str(payload.get('artifactType', '') or '').strip()
    if artifact_type not in {'host_harness_acceptance', 'host_harness_smoke'}:
        errors.append('host_harness_smoke_artifact_type_invalid')
    if not bool(payload.get('passed', False)):
        errors.append('host_harness_smoke_not_passed')
    schema_version = int(payload.get('schemaVersion', 0) or 0)
    if schema_version < 1:
        errors.append('host_harness_smoke_schema_too_old')
    return (not errors, tuple(errors), artifact_type)


def _validate_operator_docs_review(payload: dict[str, Any]) -> tuple[bool, tuple[str, ...], str]:
    errors: list[str] = []
    artifact_type = str(payload.get('artifactType', '') or '').strip()
    if artifact_type != 'operator_docs_review':
        errors.append('operator_docs_review_artifact_type_invalid')
    if not bool(payload.get('passed', False)):
        errors.append('operator_docs_review_not_passed')
    provider_name = str(payload.get('providerName', '') or '').strip()
    if provider_name != 'nav2_provider':
        errors.append('operator_docs_review_provider_mismatch')
    docs_paths = payload.get('docsPaths', [])
    required_mentions = payload.get('requiredMentions', [])
    if not isinstance(docs_paths, list) or not docs_paths:
        errors.append('operator_docs_review_missing_docs_paths')
    if not isinstance(required_mentions, list) or not required_mentions:
        errors.append('operator_docs_review_missing_required_mentions')
    return (not errors, tuple(errors), artifact_type)


def _validate_target_environment(payload: dict[str, Any], *, config_root: str | Path | None) -> tuple[bool, tuple[str, ...], str]:
    errors: list[str] = []
    artifact_type = str(payload.get('artifactType', '') or '').strip()
    if artifact_type != 'target_environment_acceptance':
        errors.append('target_environment_acceptance_artifact_type_invalid')
    validation = validate_target_environment_acceptance(payload, repo_root=Path(__file__).resolve().parents[4], config_path=config_root)
    if not validation.valid:
        errors.extend(validation.errors)
    if not bool(payload.get('passed', False)):
        errors.append('target_environment_acceptance_not_passed')
    return (not errors, tuple(errors), artifact_type)


def _validate_external_backend_smoke(payload: dict[str, Any]) -> tuple[bool, tuple[str, ...], str]:
    errors: list[str] = []
    artifact_type = str(payload.get('artifactType', '') or '').strip()
    if artifact_type != 'nav2_external_backend_smoke':
        errors.append('external_backend_smoke_artifact_type_invalid')
    if not bool(payload.get('passed', False)):
        errors.append('external_backend_smoke_not_passed')
    if str(payload.get('providerName', '') or '').strip() != 'nav2_provider':
        errors.append('external_backend_smoke_provider_mismatch')
    if str(payload.get('selectedBackend', '') or '').strip() != 'external_nav2_stack':
        errors.append('external_backend_smoke_selected_backend_mismatch')
    if not bool(payload.get('backendIntegrated', False)):
        errors.append('external_backend_smoke_backend_not_integrated')
    schema_version = int(payload.get('schemaVersion', 0) or 0)
    if schema_version < 1:
        errors.append('external_backend_smoke_schema_too_old')
    return (not errors, tuple(errors), artifact_type)


def validate_nav2_acceptance_gate(artifact_paths: Mapping[str, str] | None, *, config_root: str | Path | None = None, require_external_backend_smoke: bool = False) -> NavigationAcceptanceGate:
    paths = artifact_paths if isinstance(artifact_paths, Mapping) else {}
    required_keys = list(BASE_REQUIRED_NAV2_ARTIFACT_KEYS)
    if require_external_backend_smoke:
        required_keys.append('external_backend_smoke')
    artifacts: list[NavigationAcceptanceArtifact] = []
    aggregate_errors: list[str] = []
    for artifact_key in tuple(required_keys):
        artifact_path = str(paths.get(artifact_key, '') or '').strip()
        if not artifact_path:
            error = f'missing_path_{artifact_key}'
            artifacts.append(NavigationAcceptanceArtifact(artifact_key, '', '', False, (error,), {}))
            aggregate_errors.append(error)
            continue
        payload = _load_json_mapping(artifact_path)
        if not payload:
            error = f'unreadable_or_missing_{artifact_key}'
            artifacts.append(NavigationAcceptanceArtifact(artifact_key, artifact_path, '', False, (error,), {}))
            aggregate_errors.append(error)
            continue
        if artifact_key == 'simulation_smoke':
            valid, errors, artifact_type = _validate_smoke_artifact(payload, artifact_key=artifact_key, expected_types=('nav2_simulation_smoke', 'simulation_smoke'))
        elif artifact_key == 'host_harness_smoke':
            valid, errors, artifact_type = _validate_host_harness_artifact(payload)
        elif artifact_key == 'provider_switch_smoke':
            valid, errors, artifact_type = _validate_smoke_artifact(payload, artifact_key=artifact_key, expected_types=('nav2_provider_switch_smoke', 'provider_switch_smoke'))
        elif artifact_key == 'operator_docs_review':
            valid, errors, artifact_type = _validate_operator_docs_review(payload)
        elif artifact_key == 'target_environment_acceptance':
            valid, errors, artifact_type = _validate_target_environment(payload, config_root=config_root)
        elif artifact_key == 'external_backend_smoke':
            valid, errors, artifact_type = _validate_external_backend_smoke(payload)
        else:
            valid, errors, artifact_type = False, (f'unsupported_artifact_key_{artifact_key}',), str(payload.get('artifactType', '') or '')
        artifacts.append(NavigationAcceptanceArtifact(artifact_key, artifact_path, artifact_type, valid, errors, payload))
        aggregate_errors.extend(errors)
    return NavigationAcceptanceGate(valid=not aggregate_errors, artifacts=tuple(artifacts), errors=tuple(aggregate_errors))


def write_navigation_acceptance_artifact(output_path: str | Path, payload: Mapping[str, Any]) -> None:
    normalized_path = str(output_path or '').strip()
    if not normalized_path:
        raise ValueError('output_path is required')
    target = Path(normalized_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile('w', delete=False, dir=str(target.parent), encoding='utf-8') as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write('\n')
            temp_path = Path(handle.name)
        temp_path.replace(target)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
