from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from robot_utils.constants import HEALTH_DEGRADED, HEALTH_FAULTED, HEALTH_GOOD, READINESS_BLOCKED, READINESS_DEGRADED, READINESS_READY


@dataclass
class StatusSnapshot:
    mode: str = 'UNKNOWN'
    wifi_ok: bool = False
    camera_ok: bool = False
    audio_ok: bool = False
    uart_ok: bool = False
    bridge_ok: bool = False
    battery_voltage: float = 0.0
    battery_low_warn: bool = False
    battery_low_stop: bool = False
    left_rpm: float = 0.0
    right_rpm: float = 0.0
    control_source: str = ''
    last_qrcode: str = ''
    last_voice_cmd: str = ''
    voice_ingress_state: str = 'unknown'
    voice_ingress_reason: str = 'unseen'
    voice_ingress_source: str = ''
    last_fault: str = ''
    readiness: str = 'booting'
    readiness_reason: str = 'startup'
    health: str = HEALTH_DEGRADED
    recent_events: deque[str] = field(default_factory=lambda: deque(maxlen=12))
    snapshot_count: int = 0
    reconnect_count: int = 0
    protocol_errors: int = 0
    command_timeout_count: int = 0
    voice_reject_count: int = 0
    safe_stop_count: int = 0
    frame_drop_count: int = 0
    average_rtt_ms: float = 0.0
    bridge_queue_depth: int = 0
    last_protocol_issue: str = ''
    stale_bridge: bool = False
    stale_vision: bool = False
    stale_voice: bool = False
    stale_power: bool = False
    stale_chassis: bool = False
    last_packet_age_sec: float = 0.0


def derive_readiness(snapshot: StatusSnapshot) -> tuple[str, str]:
    if not snapshot.uart_ok:
        return READINESS_BLOCKED, 'uart_down'
    if snapshot.battery_low_stop:
        return READINESS_BLOCKED, 'battery_critical'
    if snapshot.last_fault.endswith(':fatal'):
        return READINESS_BLOCKED, 'fatal_fault'
    if snapshot.stale_chassis:
        return READINESS_BLOCKED, 'chassis_stale'
    if not snapshot.bridge_ok:
        return READINESS_DEGRADED, 'bridge_down'
    if snapshot.stale_bridge:
        return READINESS_DEGRADED, 'bridge_stale'
    if snapshot.stale_power:
        return READINESS_DEGRADED, 'power_stale'
    if snapshot.stale_vision:
        return READINESS_DEGRADED, 'vision_stale'
    if snapshot.stale_voice:
        return READINESS_DEGRADED, 'voice_stale'
    if snapshot.protocol_errors > 0:
        return READINESS_DEGRADED, 'protocol_degraded'
    if not snapshot.wifi_ok:
        return READINESS_DEGRADED, 'wifi_down'
    if not snapshot.camera_ok:
        return READINESS_DEGRADED, 'camera_down'
    if not snapshot.audio_ok:
        return READINESS_DEGRADED, 'audio_down'
    if snapshot.battery_low_warn:
        return READINESS_DEGRADED, 'battery_low_warn'
    return READINESS_READY, 'all_core_modules_ok'


def derive_health(snapshot: StatusSnapshot) -> str:
    if not snapshot.uart_ok or snapshot.battery_low_stop or snapshot.last_fault.endswith(':fatal') or snapshot.stale_chassis:
        return HEALTH_FAULTED
    if snapshot.protocol_errors > 0 or snapshot.stale_bridge or snapshot.stale_power or snapshot.stale_vision or snapshot.stale_voice or not (snapshot.wifi_ok and snapshot.camera_ok and snapshot.audio_ok and snapshot.bridge_ok) or snapshot.battery_low_warn:
        return HEALTH_DEGRADED
    return HEALTH_GOOD
