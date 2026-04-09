from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Mapping

from robot_contracts.contract_versions import now_iso

RUNTIME_PARAM_SCHEMA: dict[str, dict[str, Any]] = {
    'maxLinearSpeed': {'default': 0.45, 'min': 0.0, 'max': 1.5, 'type': float},
    'maxAngularSpeed': {'default': 1.1, 'min': 0.0, 'max': 3.5, 'type': float},
    'teleopStep': {'default': 0.08, 'min': 0.01, 'max': 0.5, 'type': float},
    'trackOffsetDeadband': {'default': 0.1, 'min': 0.0, 'max': 1.0, 'type': float},
    'lowPowerThreshold': {'default': 25, 'min': 0, 'max': 100, 'type': int},
    'reconnectTimeoutMs': {'default': 1500, 'min': 250, 'max': 10_000, 'type': int},
}

RUNTIME_PARAM_PROFILES: dict[str, dict[str, Any]] = {
    '室内保守': {
        'maxLinearSpeed': 0.26,
        'maxAngularSpeed': 0.7,
        'teleopStep': 0.06,
        'trackOffsetDeadband': 0.12,
        'lowPowerThreshold': 28,
        'reconnectTimeoutMs': 1800,
    },
    '演示标准': {key: rule['default'] for key, rule in RUNTIME_PARAM_SCHEMA.items()},
    '快速调试': {
        'maxLinearSpeed': 0.55,
        'maxAngularSpeed': 1.25,
        'teleopStep': 0.1,
        'trackOffsetDeadband': 0.09,
        'lowPowerThreshold': 22,
        'reconnectTimeoutMs': 1200,
    },
}

DEFAULT_RUNTIME_PARAM_CONSUMERS: tuple[str, ...] = ('robot_control', 'robot_decision')
RUNTIME_PARAM_MONITOR_CONSUMER = 'robot_monitor'
RUNTIME_PARAM_ACK_MODE_BEST_EFFORT = 'best_effort'
RUNTIME_PARAM_ACK_MODE_ALL = 'all_consumers'
TRANSACTION_STATE_PENDING = 'pending'
TRANSACTION_STATE_APPLIED = 'applied'
TRANSACTION_STATE_FAILED = 'failed'
TRANSACTION_STATE_TIMEOUT = 'timeout'
PARAM_PROJECTION_STATE_COMMITTED = 'committed'
PARAM_PROJECTION_STATE_PROVISIONAL = 'provisional'


class RuntimeParameterError(ValueError):
    """Raised when a runtime parameter update fails validation."""


@dataclass(slots=True)
class RuntimeParameterTransaction:
    """Tracked multi-consumer runtime-parameter apply transaction.

    The transaction preserves the command that initiated the mutation as well as
    the last stable runtime-parameter baseline. This lets the bridge emit an
    authoritative terminal ACK only after all consumers confirm the change, while
    still rolling local/frontend-visible state back on failure or timeout.
    """

    transaction_id: str = ''
    ack_mode: str = RUNTIME_PARAM_ACK_MODE_BEST_EFFORT
    expected_consumers: tuple[str, ...] = field(default_factory=lambda: DEFAULT_RUNTIME_PARAM_CONSUMERS)
    consumer_statuses: dict[str, dict[str, Any]] = field(default_factory=dict)
    deadline_ts: str | None = None
    started_at: str = field(default_factory=now_iso)
    completed_at: str | None = None
    state: str = TRANSACTION_STATE_APPLIED
    runtime_param_version: int = 0
    command_id: str = ''
    command_type: str = ''
    command_message: str = ''
    trace_id: str = ''
    rollback_params: dict[str, Any] = field(default_factory=dict)
    rollback_profile_name: str = '演示标准'
    rollback_runtime_param_version: int = 1

    def metadata(self) -> dict[str, Any]:
        return {
            'transactionId': self.transaction_id or None,
            'ackMode': self.ack_mode,
            'expectedConsumers': list(self.expected_consumers),
            'consumerStatuses': {name: dict(value) for name, value in self.consumer_statuses.items()},
            'deadlineTs': self.deadline_ts,
            'startedAt': self.started_at,
            'completedAt': self.completed_at,
            'state': self.state,
            'runtimeParamVersion': self.runtime_param_version,
            'commandId': self.command_id or None,
            'commandType': self.command_type or None,
            'commandMessage': self.command_message or None,
            'traceId': self.trace_id or None,
        }


@dataclass(slots=True)
class RuntimeParameterState:
    """Mutable runtime-parameter state mirrored by the web bridge.

    Besides the currently projected parameter set, the state also preserves the
    last committed/stable baseline so snapshots can tell the frontend whether it
    is looking at provisional or committed values.
    """

    params: dict[str, Any] = field(default_factory=lambda: runtime_param_defaults())
    active_profile_name: str = '演示标准'
    runtime_param_version: int = 1
    last_stable_params: dict[str, Any] = field(default_factory=lambda: runtime_param_defaults())
    last_stable_profile_name: str = '演示标准'
    last_stable_runtime_param_version: int = 1
    last_param_apply_result: dict[str, Any] = field(default_factory=lambda: {
        'ok': True,
        'message': 'defaults_loaded',
        'ts': now_iso(),
        'state': TRANSACTION_STATE_APPLIED,
        'projectionState': PARAM_PROJECTION_STATE_COMMITTED,
        'rollbackPerformed': False,
    })
    last_transaction: RuntimeParameterTransaction = field(default_factory=RuntimeParameterTransaction)

    def projection_state(self) -> str:
        """Return whether the current projected parameters are committed or provisional."""
        if self.last_transaction.transaction_id and self.last_transaction.state == TRANSACTION_STATE_PENDING:
            return PARAM_PROJECTION_STATE_PROVISIONAL
        return PARAM_PROJECTION_STATE_COMMITTED

    def metadata(self) -> dict[str, Any]:
        """Build runtime-parameter metadata for snapshot transport.

        Args:
            None.

        Returns:
            JSON-serializable metadata dictionary.

        Raises:
            None.
        """
        return build_runtime_param_metadata(
            self.params,
            active_profile_name=self.active_profile_name,
            runtime_param_version=self.runtime_param_version,
            last_param_apply_result=self.last_param_apply_result,
            last_transaction=self.last_transaction.metadata(),
            projection_state=self.projection_state(),
            committed_params=self.last_stable_params,
            committed_profile_name=self.last_stable_profile_name,
            committed_runtime_param_version=self.last_stable_runtime_param_version,
        )


def runtime_param_defaults() -> dict[str, Any]:
    """Return the default runtime parameter set."""
    return {key: rule['default'] for key, rule in RUNTIME_PARAM_SCHEMA.items()}


def runtime_param_profiles() -> dict[str, dict[str, Any]]:
    """Return a copy of the predefined runtime parameter profiles."""
    return {name: dict(values) for name, values in RUNTIME_PARAM_PROFILES.items()}

def runtime_param_expected_consumers(*, include_monitor: bool = False) -> tuple[str, ...]:
    """Return the authoritative runtime-parameter consumer set.

    Args:
        include_monitor: Whether monitor readiness logic must acknowledge the
            transaction before the bridge can mark the parameter projection as
            committed.

    Returns:
        Tuple of consumer identifiers in the order used for transaction
        aggregation.

    Raises:
        None.

    Boundary behavior:
        The helper keeps compatibility with legacy two-consumer deployments by
        only appending ``robot_monitor`` when explicitly requested by the
        launch/runtime surface.
    """
    if include_monitor:
        return (*DEFAULT_RUNTIME_PARAM_CONSUMERS, RUNTIME_PARAM_MONITOR_CONSUMER)
    return DEFAULT_RUNTIME_PARAM_CONSUMERS


def validate_runtime_param_key(key: str) -> str:
    """Validate a runtime parameter key."""
    normalized = str(key or '').strip()
    if normalized not in RUNTIME_PARAM_SCHEMA:
        raise RuntimeParameterError(f'unsupported runtime parameter: {normalized}')
    return normalized


def coerce_runtime_param_value(key: str, value: Any) -> Any:
    """Coerce and range-check one runtime parameter value."""
    normalized = validate_runtime_param_key(key)
    schema = RUNTIME_PARAM_SCHEMA[normalized]
    caster = schema['type']
    if isinstance(value, bool):
        raise RuntimeParameterError(f'{normalized} must be coercible to {caster.__name__}')
    try:
        converted = caster(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeParameterError(f'{normalized} must be coercible to {caster.__name__}') from exc
    if isinstance(converted, float) and not math.isfinite(converted):
        raise RuntimeParameterError(f'{normalized} must be a finite number')
    if converted < schema['min'] or converted > schema['max']:
        raise RuntimeParameterError(f'{normalized} out of range: {converted} not in [{schema["min"]}, {schema["max"]}]')
    return converted


def apply_runtime_param_update(current: Mapping[str, Any], *, key: str, value: Any) -> dict[str, Any]:
    """Apply a single runtime-parameter mutation to a parameter mapping."""
    normalized = validate_runtime_param_key(key)
    next_params = dict(runtime_param_defaults())
    next_params.update(dict(current))
    next_params[normalized] = coerce_runtime_param_value(normalized, value)
    return next_params


def apply_runtime_param_patch(current: Mapping[str, Any], *, patch: Mapping[str, Any]) -> dict[str, Any]:
    """Apply a batch runtime-parameter patch to a parameter mapping.

    Args:
        current: Current runtime-parameter mapping used as the merge baseline.
        patch: Parameter overrides keyed by runtime-parameter name. The mapping
            may be partial, but every provided key/value pair must validate
            against ``RUNTIME_PARAM_SCHEMA`` before any mutation is returned.

    Returns:
        New parameter mapping containing the validated patch.

    Raises:
        RuntimeParameterError: If ``patch`` is empty, not mapping-like, or any
            key/value pair fails validation.

    Boundary behavior:
        Validation is all-or-nothing. One invalid field aborts the entire batch
        so callers can wrap the result in a single transaction.
    """
    if not isinstance(patch, Mapping):
        raise RuntimeParameterError('runtime parameter patch must be a mapping')
    if not patch:
        raise RuntimeParameterError('runtime parameter patch must not be empty')
    next_params = dict(runtime_param_defaults())
    next_params.update(dict(current))
    validated: dict[str, Any] = {}
    for raw_key, raw_value in patch.items():
        normalized = validate_runtime_param_key(str(raw_key))
        validated[normalized] = coerce_runtime_param_value(normalized, raw_value)
    next_params.update(validated)
    return next_params


def apply_runtime_param_profile(current: Mapping[str, Any], *, profile_name: str) -> dict[str, Any]:
    """Apply a named runtime-parameter profile to a parameter mapping."""
    _ = current
    normalized = str(profile_name or '').strip()
    if normalized not in RUNTIME_PARAM_PROFILES:
        raise RuntimeParameterError(f'unsupported runtime parameter profile: {normalized}')
    next_params = dict(runtime_param_defaults())
    next_params.update(RUNTIME_PARAM_PROFILES[normalized])
    return next_params


def runtime_param_digest(params: Mapping[str, Any], *, active_profile_name: str) -> str:
    """Compute a stable digest for the runtime parameter state."""
    payload = {
        'activeProfileName': str(active_profile_name),
        'params': {key: params[key] for key in sorted(params)},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def build_runtime_param_metadata(
    params: Mapping[str, Any],
    *,
    active_profile_name: str,
    runtime_param_version: int,
    last_param_apply_result: Mapping[str, Any] | None,
    last_transaction: Mapping[str, Any] | None = None,
    projection_state: str = PARAM_PROJECTION_STATE_COMMITTED,
    committed_params: Mapping[str, Any] | None = None,
    committed_profile_name: str | None = None,
    committed_runtime_param_version: int | None = None,
) -> dict[str, Any]:
    """Build the runtime-parameter metadata payload exposed to the frontend."""
    committed_params_payload = dict(committed_params or params)
    committed_profile_value = str(committed_profile_name or active_profile_name)
    committed_version_value = int(runtime_param_version if committed_runtime_param_version is None else committed_runtime_param_version)
    return {
        'configDigest': runtime_param_digest(params, active_profile_name=active_profile_name),
        'activeProfileName': str(active_profile_name),
        'runtimeParamVersion': int(runtime_param_version),
        'lastParamApplyResult': dict(last_param_apply_result or {}),
        'lastTransaction': dict(last_transaction or {}),
        'projectionState': str(projection_state),
        'committedConfigDigest': runtime_param_digest(committed_params_payload, active_profile_name=committed_profile_value),
        'committedProfileName': committed_profile_value,
        'committedRuntimeParamVersion': committed_version_value,
    }
