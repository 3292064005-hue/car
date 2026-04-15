from __future__ import annotations

from typing import Iterable

_CANONICAL_BRIDGE_CAPABILITIES = (
    'command-ack',
    'offline-session-replay',
    'layout-presets',
    'reports-export',
    'protocol-versioning',
    'odom-bridge',
    'battery-state',
    'transport-diagnostics',
    'fault-dictionary',
    'stale-flags',
    'compatibility-mode',
    'trace-correlation',
    'runtime-param-sync',
    'mode-capability-snapshot',
    'action-workflows',
    'qos-matrix',
    'web-bridge-components',
    'frontend-slices',
    'runtime-health-snapshot',
    'command-lifecycle-v2',
)

DEPRECATED_BRIDGE_CAPABILITY_ALIASES: dict[str, str] = {}

BRIDGE_CAPABILITIES = _CANONICAL_BRIDGE_CAPABILITIES

COMMAND_LIFECYCLE_STATUSES = (
    'queued',
    'accepted',
    'applied',
    'completed',
    'rejected',
    'denied',
    'timeout',
    'cancelled',
)
COMMAND_ACK_STATUSES = ('queued', 'ack', 'rejected', 'denied', 'timeout', 'cancelled')
TERMINAL_COMMAND_ACK_STATUSES = ('ack', 'rejected', 'denied', 'timeout', 'cancelled')
TERMINAL_COMMAND_LIFECYCLE_STATUSES = ('applied', 'completed', 'rejected', 'denied', 'timeout', 'cancelled')
COMPATIBILITY_ACK_STATUS_BY_LIFECYCLE = {
    'queued': 'queued',
    'accepted': 'ack',
    'applied': 'ack',
    'completed': 'ack',
    'rejected': 'rejected',
    'denied': 'denied',
    'timeout': 'timeout',
    'cancelled': 'cancelled',
}
COMMAND_TYPES = (
    'set_mode',
    'teleop_cmd',
    'stop_now',
    'estop',
    'resume_from_safe_stop',
    'start_patrol',
    'pause_patrol',
    'stop_patrol',
    'apply_param_draft',
    'apply_param_profile',
    'speak_fixed_text',
    'reset_fault',
    'save_snapshot',
)
INBOUND_EVENT_TYPES = (
    'snapshot',
    'heartbeat',
    'connection_state',
    'mode_state',
    'chassis_state',
    'power_state',
    'vision_target',
    'vision_qrcode',
    'voice_cmd',
    'fault_event',
    'system_log',
    'task_event',
    'command_ack',
)
TRANSPORT_SUMMARY_KEYS = (
    'connected',
    'state',
    'transport_degraded',
    'rx_messages',
    'tx_messages',
    'accepted_messages',
    'ignored_messages',
    'warn_messages',
    'invalid_messages',
    'protocol_errors',
    'reconnect_count',
    'queue_depth',
    'dropped_payloads',
    'send_failures',
    'rx_age_sec',
    'tx_age_sec',
    'last_protocol_error',
    'last_rtt_ms',
    'heartbeat_age_sec',
    'inbound_rate_hz',
    'outbound_rate_hz',
    'stale_link',
    'last_disconnect_reason',
)


def compatibility_ack_status(lifecycle_status: str) -> str:
    """Map one precise lifecycle status onto the legacy ACK contract."""
    normalized = str(lifecycle_status or '').strip()
    if normalized not in COMPATIBILITY_ACK_STATUS_BY_LIFECYCLE:
        raise ValueError(f'unsupported lifecycle status: {lifecycle_status!r}')
    return COMPATIBILITY_ACK_STATUS_BY_LIFECYCLE[normalized]



def canonical_bridge_capabilities() -> tuple[str, ...]:
    """Return the canonical capability identifiers exposed by the bridge contract."""
    return _CANONICAL_BRIDGE_CAPABILITIES



def capability_alias_map() -> dict[str, str]:
    """Return deprecated capability aliases keyed by old identifier."""
    return dict(DEPRECATED_BRIDGE_CAPABILITY_ALIASES)



def supported_capabilities(extra: Iterable[str] | None = None, *, include_deprecated_aliases: bool = True) -> list[str]:
    """Return the merged supported capability list."""
    merged = list(_CANONICAL_BRIDGE_CAPABILITIES)
    if extra:
        for capability in extra:
            item = str(capability).strip()
            if item and item not in merged:
                merged.append(item)
    if include_deprecated_aliases:
        for alias in DEPRECATED_BRIDGE_CAPABILITY_ALIASES:
            if alias not in merged:
                merged.append(alias)
    return merged
