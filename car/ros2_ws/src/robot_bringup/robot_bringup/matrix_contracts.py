from __future__ import annotations

"""Structured single-source matrices for bringup capability, surfaces, and failures.

This module centralizes the profile capability matrix, surface matrix, and
failure taxonomy consumed by bringup reports and preflight. The YAML-backed
contract keeps launch profiles, diagnostics reports, and operator-facing audit
artifacts aligned instead of deriving the same facts in multiple places.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from robot_bringup.config_resolution import resolve_bringup_config
from robot_utils.config_loader import ConfigValidationError, load_structured_file

_DEFAULT_CAPABILITY_MATRIX = {
    'phases': {
        'contracts': {'requires_any': []},
        'bridge': {'requires_any': []},
        'control': {'requires_any': []},
        'monitor': {'requires_any': ['enable_monitor']},
        'platform': {'requires_any': ['enable_localization', 'enable_hardware_interface']},
        'vision_voice': {'requires_any': ['enable_vision', 'enable_voice']},
        'navigation': {'requires_any': ['enable_navigation']},
        'decision': {'requires_any': []},
        'frontend': {'requires_any': ['enable_teleop', 'enable_web_bridge', 'enable_api_server']},
    },
    'capabilities': {
        'voice': 'enable_voice',
        'vision': 'enable_vision',
        'monitor': 'enable_monitor',
        'teleop': 'enable_teleop',
        'localization': 'enable_localization',
        'navigation': 'enable_navigation',
        'hardware_interface': 'enable_hardware_interface',
        'api_server': 'enable_api_server',
        'web_bridge': 'enable_web_bridge',
        'mock_robot': 'use_mock_robot',
        'debug_overlay': 'enable_debug_overlay',
        'diagnostics': 'diagnostics_enabled',
        'preflight_checks': 'preflight_checks_enabled',
    },
}

_DEFAULT_SURFACE_MATRIX = {
    'surfaces': {
        'backend': {
            'required_nodes': ['robot_decision', 'robot_control', 'robot_bridge'],
            'ready_topics': [],
            'requires_any': [],
        },
        'web_bridge': {
            'required_nodes': ['robot_web_bridge'],
            'ready_topics': ['/robot/web_bridge/ready'],
            'requires_any': ['enable_web_bridge'],
        },
        'frontend': {
            'required_nodes': ['robot_web_bridge'],
            'ready_topics': ['/robot/web_bridge/ready'],
            'ready_http_templates': ['http://{api_probe_host}:{api_server_port}{api_server_api_prefix}/health'],
            'require_operator_ready': True,
            'requires_any': ['enable_web_bridge', 'enable_api_server'],
        },
    },
}

_DEFAULT_FAILURE_TAXONOMY = {
    'startup': {
        'missing_node': {'severity': 'fatal', 'operator_action': 'inspect_launch_and_process_logs'},
        'missing_ready_topic': {'severity': 'fatal', 'operator_action': 'wait_for_startup_barrier_or_restart_surface'},
        'preflight_failed': {'severity': 'fatal', 'operator_action': 'resolve_reported_dependency_or_config_gap'},
    },
    'runtime': {
        'bridge_runtime_degraded': {'severity': 'warn', 'operator_action': 'inspect_runtime_health_reasons_and_transport_stats'},
        'operator_surface_unready': {'severity': 'warn', 'operator_action': 'check_websocket_gateway_and_frontend_connectivity'},
        'runtime_param_timeout': {'severity': 'warn', 'operator_action': 'inspect_consumer_status_and_retry_or_rollback'},
    },
}


@dataclass(frozen=True, slots=True)
class BringupMatrices:
    capability_matrix: dict[str, Any]
    surface_matrix: dict[str, Any]
    failure_taxonomy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'capability_matrix': self.capability_matrix,
            'surface_matrix': self.surface_matrix,
            'failure_taxonomy': self.failure_taxonomy,
        }


def _matrix_path(config_path: str | None, filename: str) -> Path:
    resolved = resolve_bringup_config(config_path)
    return resolved.config_root / filename


def _validate_capability_matrix(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ConfigValidationError('capability matrix must be a mapping')
    phases = payload.get('phases', {})
    capabilities = payload.get('capabilities', {})
    if not isinstance(phases, Mapping) or not isinstance(capabilities, Mapping):
        raise ConfigValidationError('capability matrix requires mapping keys: phases, capabilities')
    normalized_phases: dict[str, dict[str, list[str]]] = {}
    for name, item in phases.items():
        if not isinstance(item, Mapping):
            raise ConfigValidationError(f'capability matrix phase {name} must be a mapping')
        requires_any = item.get('requires_any', [])
        if not isinstance(requires_any, list) or not all(isinstance(v, str) for v in requires_any):
            raise ConfigValidationError(f'capability matrix phase {name}.requires_any must be a string list')
        normalized_phases[str(name)] = {'requires_any': [str(v) for v in requires_any]}
    normalized_capabilities = {str(name): str(flag) for name, flag in capabilities.items()}
    return {'phases': normalized_phases, 'capabilities': normalized_capabilities}


def _validate_surface_matrix(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ConfigValidationError('surface matrix must be a mapping')
    surfaces = payload.get('surfaces', {})
    if not isinstance(surfaces, Mapping):
        raise ConfigValidationError('surface matrix requires mapping key: surfaces')
    normalized: dict[str, dict[str, object]] = {}
    for name, item in surfaces.items():
        if not isinstance(item, Mapping):
            raise ConfigValidationError(f'surface matrix surface {name} must be a mapping')
        required_nodes = item.get('required_nodes', [])
        ready_topics = item.get('ready_topics', [])
        ready_http_templates = item.get('ready_http_templates', [])
        requires_any = item.get('requires_any', [])
        for field_name, values in {
            'required_nodes': required_nodes,
            'ready_topics': ready_topics,
            'ready_http_templates': ready_http_templates,
            'requires_any': requires_any,
        }.items():
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ConfigValidationError(f'surface matrix {name}.{field_name} must be a string list')
        require_operator_ready = bool(item.get('require_operator_ready', False))
        normalized[str(name)] = {
            'required_nodes': [str(v) for v in required_nodes],
            'ready_topics': [str(v) for v in ready_topics],
            'ready_http_templates': [str(v) for v in ready_http_templates],
            'require_operator_ready': require_operator_ready,
            'requires_any': [str(v) for v in requires_any],
        }
    return {'surfaces': normalized}


def _validate_failure_taxonomy(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ConfigValidationError('failure taxonomy must be a mapping')
    normalized: dict[str, dict[str, dict[str, str]]] = {}
    for domain, items in payload.items():
        if not isinstance(items, Mapping):
            raise ConfigValidationError(f'failure taxonomy domain {domain} must be a mapping')
        normalized_domain: dict[str, dict[str, str]] = {}
        for code, item in items.items():
            if not isinstance(item, Mapping):
                raise ConfigValidationError(f'failure taxonomy item {domain}.{code} must be a mapping')
            severity = str(item.get('severity', '')).strip()
            operator_action = str(item.get('operator_action', '')).strip()
            if not severity or not operator_action:
                raise ConfigValidationError(f'failure taxonomy item {domain}.{code} requires severity and operator_action')
            normalized_domain[str(code)] = {'severity': severity, 'operator_action': operator_action}
        normalized[str(domain)] = normalized_domain
    return normalized


@lru_cache(maxsize=8)
def load_bringup_matrices(config_path: str | None = None) -> BringupMatrices:
    capability = load_structured_file(str(_matrix_path(config_path, 'capability_matrix.yaml')), _DEFAULT_CAPABILITY_MATRIX, context='capability matrix')
    surface = load_structured_file(str(_matrix_path(config_path, 'surface_matrix.yaml')), _DEFAULT_SURFACE_MATRIX, context='surface matrix')
    failure = load_structured_file(str(_matrix_path(config_path, 'failure_taxonomy.yaml')), _DEFAULT_FAILURE_TAXONOMY, context='failure taxonomy')
    return BringupMatrices(
        capability_matrix=_validate_capability_matrix(capability),
        surface_matrix=_validate_surface_matrix(surface),
        failure_taxonomy=_validate_failure_taxonomy(failure),
    )


def profile_feature_matrix(profile: Any, *, config_path: str | None = None) -> dict[str, bool]:
    matrices = load_bringup_matrices(config_path)
    payload: dict[str, bool] = {}
    for capability, attribute in matrices.capability_matrix['capabilities'].items():
        payload[str(capability)] = bool(getattr(profile, str(attribute), False))
    return payload


def startup_sequence_for_profile(profile: Any, *, config_path: str | None = None) -> tuple[str, ...]:
    matrices = load_bringup_matrices(config_path)
    phases: list[str] = []
    for phase_name, rule in matrices.capability_matrix['phases'].items():
        required = [str(v) for v in rule.get('requires_any', [])]
        if required and not any(bool(getattr(profile, item, False)) for item in required):
            continue
        phases.append(str(phase_name))
    return tuple(phases)


def _normalize_api_probe_host(profile: Any) -> str:
    for attr in ('api_server_public_host', 'api_server_listen_host', 'websocket_public_host', 'bridge_host'):
        value = str(getattr(profile, attr, '') or '').strip()
        if not value or value in {'0.0.0.0', '::', '::0', '*'}:
            continue
        return value
    return '127.0.0.1'


def surface_contract_for_profile(profile: Any, *, config_path: str | None = None) -> dict[str, dict[str, object]]:
    matrices = load_bringup_matrices(config_path)
    payload: dict[str, dict[str, object]] = {}
    api_probe_host = _normalize_api_probe_host(profile)
    substitutions = {
        'api_probe_host': api_probe_host,
        'api_server_port': int(getattr(profile, 'api_server_port', 9100)),
        'api_server_api_prefix': str(getattr(profile, 'api_server_api_prefix', '/api/v1') or '/api/v1'),
    }
    for name, rule in matrices.surface_matrix['surfaces'].items():
        required = [str(v) for v in rule.get('requires_any', [])]
        enabled = True if not required else any(bool(getattr(profile, item, False)) for item in required)
        payload[str(name)] = {
            'enabled': enabled,
            'required_nodes': list(rule.get('required_nodes', [])),
            'ready_topics': list(rule.get('ready_topics', [])),
            'ready_http_urls': [str(template).format(**substitutions) for template in list(rule.get('ready_http_templates', []))],
            'require_operator_ready': bool(rule.get('require_operator_ready', False)),
        }
    return payload
