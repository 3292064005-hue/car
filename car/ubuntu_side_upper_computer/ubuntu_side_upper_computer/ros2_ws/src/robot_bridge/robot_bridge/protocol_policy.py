from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from robot_bridge.json_codec import normalize_payload, validate_payload
from robot_utils.constants import (
    PROTO_ACTION_ACCEPT,
    PROTO_ACTION_FAULT,
    PROTO_ACTION_IGNORE,
    PROTO_ACTION_WARN,
)
from robot_utils.helpers import get_str

REPLAY_TYPE_ALIASES = {
    'fault_event': 'fault',
    'task_event': 'task_state',
}
REPLAYABLE_TYPES = {'voice_cmd', 'chassis_state', 'power_state', 'fault', 'system_status', 'task_state'}
IGNORED_TYPES = {'pong'}
FAULT_REASONS = ('proto_ver mismatch', 'unsupported type')


@dataclass(frozen=True)
class ProtocolDecision:
    action: str
    reason: str
    payload_type: str

    @property
    def accepted(self) -> bool:
        return self.action == PROTO_ACTION_ACCEPT


@dataclass(frozen=True)
class ReplayOptions:
    include_faults: bool = True
    include_status: bool = True
    include_voice: bool = True



def canonical_payload_type(payload: dict[str, Any]) -> str:
    raw_type = get_str(payload, 'type', '')
    return REPLAY_TYPE_ALIASES.get(raw_type, raw_type)



def classify_payload(payload: dict[str, Any]) -> ProtocolDecision:
    normalized = normalize_payload(payload)
    valid, reason = validate_payload(normalized)
    payload_type = canonical_payload_type(normalized) or 'unknown'
    if not valid:
        if any(reason.startswith(prefix) for prefix in FAULT_REASONS):
            return ProtocolDecision(PROTO_ACTION_FAULT, reason, payload_type)
        return ProtocolDecision(PROTO_ACTION_WARN, reason, payload_type)
    if payload_type in IGNORED_TYPES:
        return ProtocolDecision(PROTO_ACTION_IGNORE, 'heartbeat_ack', payload_type)
    return ProtocolDecision(PROTO_ACTION_ACCEPT, 'ok', payload_type)



def should_replay_payload(payload: dict[str, Any], *, options: ReplayOptions | None = None) -> bool:
    opts = options or ReplayOptions()
    payload_type = canonical_payload_type(normalize_payload(payload))
    if payload_type not in REPLAYABLE_TYPES:
        return False
    if payload_type == 'fault' and not opts.include_faults:
        return False
    if payload_type == 'system_status' and not opts.include_status:
        return False
    if payload_type == 'voice_cmd' and not opts.include_voice:
        return False
    return True



def filter_replay_payloads(payloads: Iterable[dict[str, Any]], *, options: ReplayOptions | None = None) -> list[dict[str, Any]]:
    return [payload for payload in payloads if should_replay_payload(payload, options=options)]
