from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

SYSTEM_REPLAY_BUNDLE_KIND = 'system-replay-bundle'
SYSTEM_REPLAY_BUNDLE_VERSION = '1.0.0'
REQUIRED_MEMBERS = ('topics', 'serviceActionEvents', 'sessionMetadata', 'traceCorrelation')
REQUIRED_SESSION_METADATA_KEYS = ('sessionId', 'profileName', 'providerName', 'hardwareRole', 'evidenceClass')
REQUIRED_HISTORY_KEYS = ('latency', 'battery', 'leftWheel', 'rightWheel', 'frameDrops', 'ackLatency')


@dataclass(frozen=True)
class SystemReplayValidation:
    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True)
class SystemReplaySessionMetadata:
    session_id: str
    profile_name: str
    provider_name: str
    hardware_role: str
    evidence_class: str

    def to_dict(self) -> dict[str, str]:
        return {
            'sessionId': self.session_id,
            'profileName': self.profile_name,
            'providerName': self.provider_name,
            'hardwareRole': self.hardware_role,
            'evidenceClass': self.evidence_class,
        }


class SystemReplayAutoCapture:
    """Collect bounded runtime evidence and export a validated replay bundle."""

    def __init__(self, *, history_limit: int = 120, log_limit: int = 256, trace_limit: int = 128) -> None:
        self._history_limit = max(1, int(history_limit))
        self._logs = deque(maxlen=max(1, int(log_limit)))
        self._topics = deque(maxlen=max(1, int(log_limit)))
        self._trace = deque(maxlen=max(1, int(trace_limit)))
        self._service_action = deque(maxlen=max(1, int(trace_limit)))
        self._commands = deque(maxlen=max(1, int(trace_limit)))
        self._inspector = deque(maxlen=max(1, int(trace_limit)))
        self._history = {key: deque(maxlen=self._history_limit) for key in REQUIRED_HISTORY_KEYS}

    def append_history_sample(
        self,
        *,
        latency_ms: float,
        battery_percent: float,
        left_wheel: float,
        right_wheel: float,
        frame_drops: float,
        ack_latency_ms: float,
    ) -> None:
        self._history['latency'].append(float(latency_ms))
        self._history['battery'].append(float(battery_percent))
        self._history['leftWheel'].append(float(left_wheel))
        self._history['rightWheel'].append(float(right_wheel))
        self._history['frameDrops'].append(float(frame_drops))
        self._history['ackLatency'].append(float(ack_latency_ms))

    def record_log(self, payload: dict[str, Any]) -> None:
        self._logs.append(dict(payload))

    def record_topic(self, payload: dict[str, Any]) -> None:
        self._topics.append(dict(payload))

    def record_trace(self, payload: dict[str, Any]) -> None:
        self._trace.append(dict(payload))

    def record_service_action_event(self, payload: dict[str, Any]) -> None:
        self._service_action.append(dict(payload))

    def record_command(self, payload: dict[str, Any]) -> None:
        self._commands.append(dict(payload))

    def record_inspector_trace(self, payload: dict[str, Any]) -> None:
        self._inspector.append(dict(payload))

    def history_payload(self) -> dict[str, list[float]]:
        return {key: list(values) for key, values in self._history.items()}

    def build_payload(
        self,
        *,
        source_name: str,
        session_metadata: dict[str, Any],
        params: dict[str, Any],
        exported_at: str = '',
    ) -> dict[str, Any]:
        return build_system_replay_bundle(
            source_name=source_name,
            session_metadata=session_metadata,
            topics=list(self._topics),
            service_action_events=list(self._service_action),
            trace_correlation=list(self._trace),
            logs=list(self._logs),
            history=self.history_payload(),
            params=dict(params),
            commands=list(self._commands),
            inspector_trace=list(self._inspector),
            exported_at=exported_at,
        )

    def export_bundle(
        self,
        output_path: str | Path,
        *,
        source_name: str,
        session_metadata: dict[str, Any],
        params: dict[str, Any],
        exported_at: str = '',
    ) -> dict[str, Any]:
        payload = self.build_payload(
            source_name=source_name,
            session_metadata=session_metadata,
            params=params,
            exported_at=exported_at,
        )
        validation = validate_system_replay_bundle(payload)
        if not validation.valid:
            raise ValueError(f'invalid system replay bundle: {validation.errors}')
        atomic_write_json(output_path, payload)
        return payload


def build_runtime_session_metadata(
    *,
    session_id: str,
    profile_name: str,
    provider_name: str,
    hardware_role: str,
    evidence_class: str,
) -> dict[str, str]:
    return SystemReplaySessionMetadata(
        session_id=str(session_id or '').strip() or 'runtime-session',
        profile_name=str(profile_name or '').strip() or 'unknown',
        provider_name=str(provider_name or '').strip() or 'simple_nav_provider',
        hardware_role=str(hardware_role or '').strip() or 'ros_projection_only',
        evidence_class=str(evidence_class or '').strip() or 'host_harness_only',
    ).to_dict()


def load_json_or_default(path_value: str | Path | None, *, default: Any) -> Any:
    path = Path(str(path_value or '').strip())
    if not str(path_value or '').strip() or not path.is_file():
        return default
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default
    return payload


def build_system_replay_bundle(
    *,
    source_name: str,
    session_metadata: dict[str, Any],
    topics: list[dict[str, Any]],
    service_action_events: list[dict[str, Any]],
    trace_correlation: list[dict[str, Any]],
    logs: list[dict[str, Any]],
    history: dict[str, Any],
    params: dict[str, Any],
    commands: list[dict[str, Any]] | None = None,
    inspector_trace: list[dict[str, Any]] | None = None,
    exported_at: str = '',
) -> dict[str, Any]:
    return {
        'kind': SYSTEM_REPLAY_BUNDLE_KIND,
        'exportScope': 'system-evidence',
        'exportedAt': exported_at,
        'sourceName': source_name,
        'version': SYSTEM_REPLAY_BUNDLE_VERSION,
        'sessionMetadata': session_metadata,
        'topics': topics,
        'serviceActionEvents': service_action_events,
        'traceCorrelation': trace_correlation,
        'logs': logs,
        'history': history,
        'params': params,
        'commands': list(commands or []),
        'inspectorTrace': list(inspector_trace or []),
    }


def build_system_replay_bundle_from_runtime_artifacts(
    runtime_dir: str | Path,
    *,
    profile_name: str,
    provider_name: str,
    hardware_role: str,
    evidence_class: str,
) -> dict[str, Any]:
    runtime_root = Path(str(runtime_dir))
    metrics = load_json_or_default(runtime_root / 'metrics.json', default={})
    evidence = load_json_or_default(runtime_root / 'evidence_index.json', default={})
    events_path = runtime_root / 'events.jsonl'
    logs: list[dict[str, Any]] = []
    if events_path.is_file():
        for line in events_path.read_text(encoding='utf-8', errors='replace').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                logs.append(payload)
    history = {
        'latency': list(metrics.get('latencyHistory', [])) if isinstance(metrics, dict) else [],
        'battery': list(metrics.get('batteryHistory', [])) if isinstance(metrics, dict) else [],
        'leftWheel': list(metrics.get('leftWheelHistory', [])) if isinstance(metrics, dict) else [],
        'rightWheel': list(metrics.get('rightWheelHistory', [])) if isinstance(metrics, dict) else [],
        'frameDrops': list(metrics.get('frameDropHistory', [])) if isinstance(metrics, dict) else [],
        'ackLatency': list(metrics.get('ackLatencyHistory', [])) if isinstance(metrics, dict) else [],
    }
    return build_system_replay_bundle(
        source_name='runtime-artifact-builder',
        session_metadata=build_runtime_session_metadata(
            session_id=f'{profile_name}-runtime-artifacts',
            profile_name=profile_name,
            provider_name=provider_name,
            hardware_role=hardware_role,
            evidence_class=evidence_class,
        ),
        topics=list(evidence.get('runtimeTopics', [])) if isinstance(evidence, dict) else [],
        service_action_events=list(evidence.get('serviceActionEvents', [])) if isinstance(evidence, dict) else [],
        trace_correlation=list(evidence.get('traceCorrelation', [])) if isinstance(evidence, dict) else [],
        logs=logs,
        history=history,
        params=dict(evidence.get('runtimeParams', {})) if isinstance(evidence, dict) else {},
        commands=list(evidence.get('commands', [])) if isinstance(evidence, dict) else [],
        inspector_trace=list(evidence.get('inspectorTrace', [])) if isinstance(evidence, dict) else [],
    )


def validate_system_replay_bundle(payload: dict[str, Any]) -> SystemReplayValidation:
    errors: list[str] = []
    if str(payload.get('kind', '') or '').strip() != SYSTEM_REPLAY_BUNDLE_KIND:
        errors.append('kind_mismatch')
    if str(payload.get('exportScope', '') or '').strip() != 'system-evidence':
        errors.append('export_scope_mismatch')
    if not str(payload.get('sourceName', '') or '').strip():
        errors.append('missing_source_name')
    if not str(payload.get('version', '') or '').strip():
        errors.append('missing_version')
    for member in REQUIRED_MEMBERS:
        if member not in payload:
            errors.append(f'missing_{member}')
    session_metadata = payload.get('sessionMetadata')
    if 'sessionMetadata' in payload and not isinstance(session_metadata, dict):
        errors.append('session_metadata_not_mapping')
    elif isinstance(session_metadata, dict):
        for key in REQUIRED_SESSION_METADATA_KEYS:
            if not str(session_metadata.get(key, '') or '').strip():
                errors.append(f'missing_session_metadata_{key}')
    for list_member in ('topics', 'serviceActionEvents', 'traceCorrelation', 'logs'):
        if list_member in payload and not isinstance(payload.get(list_member), list):
            errors.append(f'{list_member}_not_list')
    history = payload.get('history')
    if 'history' in payload and not isinstance(history, dict):
        errors.append('history_not_mapping')
    elif isinstance(history, dict):
        for key in REQUIRED_HISTORY_KEYS:
            if key not in history:
                errors.append(f'missing_history_{key}')
            elif not isinstance(history.get(key), list):
                errors.append(f'history_{key}_not_list')
    if 'params' in payload and not isinstance(payload.get('params'), dict):
        errors.append('params_not_mapping')
    return SystemReplayValidation(valid=not errors, errors=tuple(errors))


def atomic_write_json(output_path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(str(output_path))
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile('w', delete=False, dir=str(target.parent), encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write('\n')
            temp_path = Path(handle.name)
        temp_path.replace(target)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
