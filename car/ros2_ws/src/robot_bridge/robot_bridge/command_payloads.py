from __future__ import annotations

from typing import Any

from robot_utils.constants import PROTO_VER
from robot_utils.legacy_compat_audit import record_motion_input_alias_hit
from robot_utils.helpers import get_float, get_int, safe_json_dumps, unix_time

from .payload_types import CMD_VEL, SET_MODE, SPEAK


CANONICAL_MOTION_FIELDS = ('vx', 'wz')
LEGACY_MOTION_FIELDS = ('linear', 'angular')


def build_cmd_vel_payload(*, seq: int, vx: float, wz: float, mode: str, timestamp: float | None = None) -> dict[str, Any]:
    ts = unix_time() if timestamp is None else timestamp
    vx = round(float(vx), 4)
    wz = round(float(wz), 4)
    return {
        'type': CMD_VEL,
        'proto_ver': PROTO_VER,
        'seq': int(seq),
        'timestamp': float(ts),
        'mode': mode,
        'vx': vx,
        'wz': wz,
    }


def build_mode_payload(*, seq: int, mode: str, requested_by: str, reason: str, timestamp: float | None = None) -> dict[str, Any]:
    ts = unix_time() if timestamp is None else timestamp
    return {
        'type': SET_MODE,
        'proto_ver': PROTO_VER,
        'seq': int(seq),
        'timestamp': float(ts),
        'mode': mode,
        'requested_by': requested_by,
        'reason': reason,
    }


def build_speak_payload(*, seq: int, text_id: str, priority: int, requested_by: str, timestamp: float | None = None) -> dict[str, Any]:
    ts = unix_time() if timestamp is None else timestamp
    return {
        'type': SPEAK,
        'proto_ver': PROTO_VER,
        'seq': int(seq),
        'timestamp': float(ts),
        'text_id': text_id,
        'priority': int(priority),
        'requested_by': requested_by,
    }


def motion_from_payload(payload: dict[str, Any]) -> tuple[float, float]:
    """Decode motion values from either canonical or legacy fields."""
    vx = get_float(payload, 'vx', None)
    wz = get_float(payload, 'wz', None)
    if vx is None:
        vx = get_float(payload, 'linear', 0.0)
    if wz is None:
        wz = get_float(payload, 'angular', 0.0)
    return float(vx), float(wz)


def normalize_motion_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize motion payloads onto canonical fields while tolerating legacy input.

    Args:
        payload: Motion payload that may still contain ``linear``/``angular`` aliases.

    Returns:
        Canonicalized payload containing ``vx``/``wz`` plus required transport fields.

    Raises:
        None. Invalid numeric coercion is delegated to :func:`motion_from_payload`.
    """
    normalized = dict(payload)
    legacy_fields = [field for field in LEGACY_MOTION_FIELDS if field in payload]
    if legacy_fields:
        record_motion_input_alias_hit(legacy_fields, detail='cmd_vel payload normalized onto canonical vx/wz fields')
    vx, wz = motion_from_payload(payload)
    normalized['vx'] = round(vx, 4)
    normalized['wz'] = round(wz, 4)
    normalized.pop('linear', None)
    normalized.pop('angular', None)
    normalized['seq'] = get_int(normalized, 'seq', 0)
    normalized.setdefault('proto_ver', PROTO_VER)
    return normalized


def payload_summary(payload: dict[str, Any]) -> str:
    return safe_json_dumps(normalize_motion_payload(payload) if payload.get('type') == CMD_VEL else payload)
