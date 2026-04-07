from __future__ import annotations

from typing import Any

from robot_utils.constants import PROTO_VER
from robot_utils.helpers import get_float, get_int, safe_json_dumps, unix_time


CANONICAL_MOTION_FIELDS = ('vx', 'wz')
LEGACY_MOTION_FIELDS = ('linear', 'angular')


def build_cmd_vel_payload(*, seq: int, vx: float, wz: float, mode: str, timestamp: float | None = None) -> dict[str, Any]:
    ts = unix_time() if timestamp is None else timestamp
    vx = round(float(vx), 4)
    wz = round(float(wz), 4)
    return {
        'type': 'cmd_vel',
        'proto_ver': PROTO_VER,
        'seq': int(seq),
        'timestamp': float(ts),
        'mode': mode,
        # canonical contract
        'vx': vx,
        'wz': wz,
        # compatibility aliases for legacy mock / tools
        'linear': vx,
        'angular': wz,
    }


def build_mode_payload(*, seq: int, mode: str, requested_by: str, reason: str, timestamp: float | None = None) -> dict[str, Any]:
    ts = unix_time() if timestamp is None else timestamp
    return {
        'type': 'set_mode',
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
        'type': 'speak',
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
    normalized = dict(payload)
    vx, wz = motion_from_payload(payload)
    normalized['vx'] = round(vx, 4)
    normalized['wz'] = round(wz, 4)
    normalized.setdefault('linear', normalized['vx'])
    normalized.setdefault('angular', normalized['wz'])
    normalized['seq'] = get_int(normalized, 'seq', 0)
    normalized.setdefault('proto_ver', PROTO_VER)
    return normalized


def payload_summary(payload: dict[str, Any]) -> str:
    return safe_json_dumps(normalize_motion_payload(payload) if payload.get('type') == 'cmd_vel' else payload)
