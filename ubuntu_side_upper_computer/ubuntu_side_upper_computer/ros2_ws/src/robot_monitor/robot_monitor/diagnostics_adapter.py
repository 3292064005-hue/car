from __future__ import annotations

import json
from typing import Any

from robot_monitor.status_aggregator import StatusSnapshot, derive_health, derive_readiness

try:  # pragma: no cover
    from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue  # type: ignore
except Exception:  # pragma: no cover
    DiagnosticArray = DiagnosticStatus = KeyValue = None

LEVEL_OK = 0
LEVEL_WARN = 1
LEVEL_ERROR = 2
LEVEL_STALE = 3



def _make_status(name: str, level: int, message: str, values: dict[str, Any]) -> Any:
    if DiagnosticStatus is None:
        payload = {'name': name, 'level': level, 'message': message, **values}
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    status = DiagnosticStatus()
    status.name = name
    status.hardware_id = 'inspection_robot'
    status.message = message
    status.level = level
    status.values = []
    for key, value in values.items():
        kv = KeyValue()
        kv.key = key
        kv.value = str(value)
        status.values.append(kv)
    return status



def make_diagnostic_status(snapshot: StatusSnapshot, *, name: str = 'inspection_robot/system') -> Any:
    readiness, reason = derive_readiness(snapshot)
    health = derive_health(snapshot)
    level = LEVEL_ERROR if health == 'faulted' else LEVEL_WARN if health == 'degraded' else LEVEL_OK
    return _make_status(name, level, reason, {
        'mode': snapshot.mode,
        'readiness': readiness,
        'health': health,
        'battery_voltage': f'{snapshot.battery_voltage:.2f}',
        'control_source': snapshot.control_source,
        'last_fault': snapshot.last_fault,
        'snapshot_count': snapshot.snapshot_count,
        'reconnect_count': snapshot.reconnect_count,
        'protocol_errors': snapshot.protocol_errors,
        'last_protocol_issue': snapshot.last_protocol_issue,
        'stale_bridge': snapshot.stale_bridge,
        'stale_vision': snapshot.stale_vision,
        'stale_voice': snapshot.stale_voice,
        'last_packet_age_sec': snapshot.last_packet_age_sec,
    })



def _component_level(ok: bool, *, stale: bool = False, error: bool = False) -> int:
    if error:
        return LEVEL_ERROR
    if stale:
        return LEVEL_STALE
    return LEVEL_OK if ok else LEVEL_WARN



def make_diagnostic_statuses(snapshot: StatusSnapshot) -> list[Any]:
    system = make_diagnostic_status(snapshot)
    component_specs = [
        (
            'inspection_robot/bridge',
            _component_level(snapshot.bridge_ok and snapshot.protocol_errors == 0, stale=snapshot.stale_bridge, error=snapshot.protocol_errors > 0),
            {
                'protocol_errors': snapshot.protocol_errors,
                'reconnect_count': snapshot.reconnect_count,
                'last_protocol_issue': snapshot.last_protocol_issue,
                'stale_bridge': snapshot.stale_bridge,
                'last_packet_age_sec': snapshot.last_packet_age_sec,
            },
        ),
        ('inspection_robot/wifi', _component_level(snapshot.wifi_ok), {}),
        ('inspection_robot/camera', _component_level(snapshot.camera_ok, stale=snapshot.stale_vision), {'stale_vision': snapshot.stale_vision}),
        ('inspection_robot/audio', _component_level(snapshot.audio_ok, stale=snapshot.stale_voice), {'stale_voice': snapshot.stale_voice}),
        (
            'inspection_robot/power',
            _component_level(not snapshot.battery_low_stop, error=snapshot.battery_low_stop or not snapshot.uart_ok),
            {'battery_voltage': f'{snapshot.battery_voltage:.2f}', 'low_warn': snapshot.battery_low_warn, 'low_stop': snapshot.battery_low_stop},
        ),
        ('inspection_robot/control', _component_level(snapshot.control_source != ''), {'control_source': snapshot.control_source, 'mode': snapshot.mode}),
    ]
    statuses = [system]
    for name, level, values in component_specs:
        message = 'ok' if level == LEVEL_OK else 'stale' if level == LEVEL_STALE else 'error' if level == LEVEL_ERROR else 'degraded'
        statuses.append(_make_status(name, level, message, values))
    return statuses



def diagnostic_transport_type() -> str:
    return 'diagnostic_array' if DiagnosticArray is not None else 'json_string'
