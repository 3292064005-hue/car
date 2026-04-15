from __future__ import annotations

import json
from typing import Any, Mapping

from robot_contracts.runtime_parameters import (
    DEFAULT_RUNTIME_PARAM_CONSUMERS,
    RUNTIME_PARAM_ACK_MODE_ALL,
    RUNTIME_PARAM_ACK_MODE_BEST_EFFORT,
    runtime_param_authoritative_defaults,
    runtime_param_authoritative_view,
)

RUNTIME_PARAM_TOPIC = '/robot/runtime_params'
RUNTIME_PARAM_APPLY_RESULT_TOPIC = '/robot/runtime_param_apply_result'
RUNTIME_PARAM_SOURCE = 'robot_web_bridge'


class RuntimeParamTransportError(ValueError):
    """Raised when a runtime-parameter transport payload is malformed."""



def _coerce_int_field(payload: Mapping[str, Any], field_name: str, *, default: int = 0) -> int:
    """Coerce one integer transport field with a transport-specific error.

    Args:
        payload: Parsed JSON payload.
        field_name: Integer field name.
        default: Default value used when the field is absent or empty.

    Returns:
        Parsed integer value.

    Raises:
        RuntimeParamTransportError: If the field cannot be parsed as an integer.
    """
    raw_value = payload.get(field_name, default)
    if raw_value in (None, ''):
        raw_value = default
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise RuntimeParamTransportError(f'{field_name} must be an integer') from exc



def _normalize_string_list(payload: Mapping[str, Any], field_name: str, *, default: tuple[str, ...] | list[str] = ()) -> list[str]:
    """Normalize one array-of-strings transport field."""
    raw_values = payload.get(field_name, default)
    if raw_values in (None, ''):
        raw_values = default
    if not isinstance(raw_values, (list, tuple)):
        raise RuntimeParamTransportError(f'{field_name} must be an array of strings')
    return [str(item) for item in raw_values if str(item or '').strip()]



def _normalize_expected_consumers(payload: Mapping[str, Any]) -> list[str]:
    """Normalize expected consumer identifiers from one transport payload.

    Args:
        payload: Parsed JSON payload.

    Returns:
        List of normalized consumer names.

    Raises:
        RuntimeParamTransportError: If the value is not a JSON array of strings.
    """
    normalized = _normalize_string_list(payload, 'expected_consumers', default=DEFAULT_RUNTIME_PARAM_CONSUMERS)
    return normalized or list(DEFAULT_RUNTIME_PARAM_CONSUMERS)



def build_runtime_param_payload(
    params: Mapping[str, Any],
    *,
    active_profile_name: str,
    runtime_param_version: int,
    reason: str,
    ts: str,
    trace_id: str = '',
    source: str = RUNTIME_PARAM_SOURCE,
    transaction_id: str = '',
    ack_mode: str = RUNTIME_PARAM_ACK_MODE_BEST_EFFORT,
    expected_consumers: tuple[str, ...] | list[str] | None = None,
    authoritative_keys: tuple[str, ...] | list[str] | None = None,
    ignored_frontend_local_keys: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable runtime-parameter synchronization payload.

    The transport payload intentionally carries only backend-authoritative
    runtime parameters. Browser-local fields stay in frontend session storage and
    are surfaced through snapshot/profile metadata instead of backend fan-out.
    """
    merged = dict(runtime_param_authoritative_defaults())
    merged.update(runtime_param_authoritative_view(params))
    consumers = tuple(expected_consumers or DEFAULT_RUNTIME_PARAM_CONSUMERS)
    return {
        'source': str(source),
        'trace_id': str(trace_id or ''),
        'transaction_id': str(transaction_id or ''),
        'ack_mode': str(ack_mode or RUNTIME_PARAM_ACK_MODE_BEST_EFFORT),
        'expected_consumers': [str(item) for item in consumers if str(item or '').strip()],
        'authoritative_keys': [str(item) for item in tuple(authoritative_keys or ()) if str(item or '').strip()],
        'ignored_frontend_local_keys': [str(item) for item in tuple(ignored_frontend_local_keys or ()) if str(item or '').strip()],
        'active_profile_name': str(active_profile_name),
        'runtime_param_version': int(runtime_param_version),
        'reason': str(reason),
        'ts': str(ts),
        'params': merged,
    }



def build_runtime_param_apply_result(
    *,
    consumer: str,
    transaction_id: str,
    runtime_param_version: int,
    ok: bool,
    message: str,
    ts: str,
    trace_id: str = '',
) -> dict[str, Any]:
    """Build one consumer apply-result payload for runtime-parameter fan-out."""
    return {
        'consumer': str(consumer),
        'transaction_id': str(transaction_id or ''),
        'runtime_param_version': int(runtime_param_version),
        'ok': bool(ok),
        'message': str(message),
        'ts': str(ts),
        'trace_id': str(trace_id or ''),
    }



def dumps_runtime_param_payload(payload: Mapping[str, Any]) -> str:
    """Serialize a runtime-parameter payload."""
    return json.dumps(dict(payload), ensure_ascii=False, separators=(',', ':'))



def dumps_runtime_param_apply_result(payload: Mapping[str, Any]) -> str:
    """Serialize one runtime-parameter apply-result payload."""
    return json.dumps(dict(payload), ensure_ascii=False, separators=(',', ':'))



def loads_runtime_param_payload(raw: str) -> dict[str, Any]:
    """Parse and validate a runtime-parameter synchronization payload."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeParamTransportError(f'invalid runtime parameter payload json: {exc.msg}') from exc
    if not isinstance(payload, dict):
        raise RuntimeParamTransportError('runtime parameter payload root must be an object')
    params = payload.get('params')
    if not isinstance(params, dict):
        raise RuntimeParamTransportError('runtime parameter payload must contain params object')
    merged = dict(runtime_param_authoritative_defaults())
    merged.update(runtime_param_authoritative_view(params))
    payload['params'] = merged
    payload['active_profile_name'] = str(payload.get('active_profile_name', '自定义') or '自定义')
    payload['runtime_param_version'] = _coerce_int_field(payload, 'runtime_param_version', default=0)
    payload['reason'] = str(payload.get('reason', '') or '')
    payload['trace_id'] = str(payload.get('trace_id', '') or '')
    payload['transaction_id'] = str(payload.get('transaction_id', '') or '')
    payload['ack_mode'] = str(payload.get('ack_mode', RUNTIME_PARAM_ACK_MODE_BEST_EFFORT) or RUNTIME_PARAM_ACK_MODE_BEST_EFFORT)
    if payload['ack_mode'] == 'all':
        payload['ack_mode'] = RUNTIME_PARAM_ACK_MODE_ALL
    if payload['ack_mode'] not in {RUNTIME_PARAM_ACK_MODE_BEST_EFFORT, RUNTIME_PARAM_ACK_MODE_ALL}:
        raise RuntimeParamTransportError('ack_mode is unsupported')
    payload['expected_consumers'] = _normalize_expected_consumers(payload)
    payload['authoritative_keys'] = _normalize_string_list(payload, 'authoritative_keys')
    payload['ignored_frontend_local_keys'] = _normalize_string_list(payload, 'ignored_frontend_local_keys')
    payload['source'] = str(payload.get('source', RUNTIME_PARAM_SOURCE) or RUNTIME_PARAM_SOURCE)
    payload['ts'] = str(payload.get('ts', '') or '')
    return payload



def loads_runtime_param_apply_result(raw: str) -> dict[str, Any]:
    """Parse and validate one runtime-parameter apply-result payload."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeParamTransportError(f'invalid runtime parameter apply-result json: {exc.msg}') from exc
    if not isinstance(payload, dict):
        raise RuntimeParamTransportError('runtime parameter apply-result root must be an object')
    payload['consumer'] = str(payload.get('consumer', '') or '')
    if not payload['consumer']:
        raise RuntimeParamTransportError('runtime parameter apply-result must contain consumer')
    payload['transaction_id'] = str(payload.get('transaction_id', '') or '')
    if not payload['transaction_id']:
        raise RuntimeParamTransportError('runtime parameter apply-result must contain transaction_id')
    payload['runtime_param_version'] = _coerce_int_field(payload, 'runtime_param_version', default=0)
    payload['ok'] = bool(payload.get('ok', False))
    payload['message'] = str(payload.get('message', '') or '')
    payload['trace_id'] = str(payload.get('trace_id', '') or '')
    payload['ts'] = str(payload.get('ts', '') or '')
    return payload
