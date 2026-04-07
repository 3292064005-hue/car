from __future__ import annotations

import json
from typing import Any

from robot_bridge.command_payloads import normalize_motion_payload
from robot_contracts.bridge_contract import TCP_PROTOCOL_VERSION, validate_transport_proto_version
from robot_utils.helpers import get_int, get_str

PAYLOAD_TYPE_ALIASES = {
    'task_event': 'task_state',
    'fault_event': 'fault',
}

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    'voice_cmd': ('type', 'cmd'),
    'cmd_vel': ('type', 'seq', 'mode'),
    'chassis_state': ('type', 'left_rpm', 'right_rpm'),
    'power_state': ('type', 'battery_voltage'),
    'fault': ('type', 'code', 'level'),
    'system_status': ('type', 'wifi_ok', 'camera_ok', 'audio_ok', 'uart_ok'),
    'pong': ('type', 'seq'),
    'task_state': ('type', 'current_step_name', 'patrol_index', 'mode'),
}

SUPPORTED_TYPES = tuple(REQUIRED_FIELDS.keys())


def decode_line(line: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload



def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    payload_type = PAYLOAD_TYPE_ALIASES.get(get_str(normalized, 'type'), get_str(normalized, 'type'))
    if payload_type:
        normalized['type'] = payload_type
    if payload_type == 'cmd_vel':
        normalized = normalize_motion_payload(normalized)
    if payload_type == 'system_status':
        if 'batteryVoltage' in normalized and 'battery_voltage' not in normalized:
            normalized['battery_voltage'] = normalized['batteryVoltage']
        if 'currentMode' in normalized and 'current_mode' not in normalized:
            normalized['current_mode'] = normalized['currentMode']
        if 'low_warn' in normalized and 'low_power_warn' not in normalized:
            normalized['low_power_warn'] = normalized['low_warn']
        if 'low_stop' in normalized and 'low_power_stop' not in normalized:
            normalized['low_power_stop'] = normalized['low_stop']
    if 'protoVersion' in normalized and 'proto_ver' not in normalized:
        normalized['proto_ver'] = normalized['protoVersion']
    normalized.setdefault('proto_ver', TCP_PROTOCOL_VERSION)
    normalized.setdefault('timestamp', 0.0)
    return normalized



def validate_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    payload = normalize_payload(payload)
    ptype = get_str(payload, 'type')
    if not ptype:
        return False, 'missing type'
    required = REQUIRED_FIELDS.get(ptype)
    if required is None:
        return False, f'unsupported type: {ptype}'
    for field in required:
        if field not in payload:
            return False, f'missing field: {field}'
    proto_ver = get_int(payload, 'proto_ver', TCP_PROTOCOL_VERSION)
    if not validate_transport_proto_version(proto_ver, transport='tcp'):
        return False, f'proto_ver mismatch: {proto_ver}'
    return True, 'ok'
