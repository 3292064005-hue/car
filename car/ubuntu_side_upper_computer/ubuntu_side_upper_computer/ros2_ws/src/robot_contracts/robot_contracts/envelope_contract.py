from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping
from uuid import uuid4

from robot_contracts.capabilities import (
    BRIDGE_CAPABILITIES,
    COMMAND_ACK_STATUSES,
    COMMAND_LIFECYCLE_STATUSES,
    COMMAND_TYPES,
    TRANSPORT_SUMMARY_KEYS,
    compatibility_ack_status,
)
from robot_contracts.command_policy import COMMAND_PERMISSION_MATRIX, ContractCheckResult
from robot_contracts.contract_versions import COMPATIBILITY_MODES, CONTRACT_VERSIONS, DEFAULT_SESSION_ID, PROTOCOL_VERSION, SCHEMA_VERSION, now_iso, resolve_compatibility_mode
from robot_contracts.runtime_parameters import RUNTIME_PARAM_PROFILES, RUNTIME_PARAM_SCHEMA


class EnvelopeValidationError(ValueError):
    """Raised when a bridge envelope or runtime contract payload is invalid."""


@dataclass(slots=True)
class BridgeEnvelope:
    type: str
    payload: dict[str, Any]
    source: str = 'bridge'
    session_id: str = DEFAULT_SESSION_ID
    seq: int = 0
    event_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    ts: str = field(default_factory=lambda: now_iso())
    protocol_version: str = PROTOCOL_VERSION
    schema_version: str = SCHEMA_VERSION
    capabilities: tuple[str, ...] = BRIDGE_CAPABILITIES
    compatibility_mode: str = 'native-v4'

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            'eventId': payload['event_id'],
            'traceId': payload['trace_id'],
            'type': payload['type'],
            'ts': payload['ts'],
            'source': payload['source'],
            'sessionId': payload['session_id'],
            'seq': payload['seq'],
            'payload': payload['payload'],
            'protocolVersion': payload['protocol_version'],
            'schemaVersion': payload['schema_version'],
            'compatibilityMode': payload['compatibility_mode'],
            'capabilities': list(payload['capabilities']),
        }


@dataclass(frozen=True, slots=True)
class CommandAck:
    command_id: str
    status: str
    message: str
    detail: str = ''
    trace_id: str = ''
    lifecycle_status: str = ''

    def to_payload(self) -> dict[str, Any]:
        """Serialize one command acknowledgement payload.

        Args:
            None.

        Returns:
            Bridge-compatible acknowledgement payload.

        Raises:
            EnvelopeValidationError: If either the legacy compatibility status or
                the precise lifecycle status is unsupported.
        """
        if self.status not in COMMAND_ACK_STATUSES:
            raise EnvelopeValidationError(f'unsupported command ack status: {self.status}')
        lifecycle_status = str(self.lifecycle_status or '').strip()
        if lifecycle_status:
            if lifecycle_status not in COMMAND_LIFECYCLE_STATUSES:
                raise EnvelopeValidationError(f'unsupported command lifecycle status: {lifecycle_status}')
            expected_status = compatibility_ack_status(lifecycle_status)
            if self.status != expected_status:
                raise EnvelopeValidationError(
                    f'command ack status {self.status!r} does not match lifecycle status {lifecycle_status!r}'
                )
        payload = {
            'commandId': self.command_id,
            'status': self.status,
            'message': self.message,
        }
        if lifecycle_status:
            payload['lifecycleStatus'] = lifecycle_status
        if self.detail:
            payload['detail'] = self.detail
        if self.trace_id:
            payload['traceId'] = self.trace_id
        return payload




def ensure_event_type(event_type: str) -> str:
    """Validate that an event type is present.

    Args:
        event_type: Raw event type string.

    Returns:
        Normalized event type string.

    Raises:
        EnvelopeValidationError: If the event type is empty.
    """
    value = str(event_type or '').strip()
    if not value:
        raise EnvelopeValidationError('event type must be non-empty')
    return value



def make_envelope(
    event_type: str,
    payload: dict[str, Any],
    *,
    source: str = 'bridge',
    session_id: str = DEFAULT_SESSION_ID,
    seq: int = 0,
    compatibility_mode: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Build a contract-compliant bridge envelope.

    Args:
        event_type: Outbound event type.
        payload: Event payload mapping.
        source: Event source label.
        session_id: Session identifier.
        seq: Monotonic sequence number.
        compatibility_mode: Optional compatibility mode override.
        trace_id: Optional trace identifier override.

    Returns:
        JSON-serializable envelope dictionary.

    Raises:
        EnvelopeValidationError: If the event type is empty.
    """
    ensure_event_type(event_type)
    mode = compatibility_mode or resolve_compatibility_mode(PROTOCOL_VERSION)
    envelope = BridgeEnvelope(type=event_type, payload=payload, source=source, session_id=session_id, seq=seq, compatibility_mode=mode)
    if trace_id:
        envelope.trace_id = trace_id
    return envelope.to_dict()



def validate_envelope_dict(payload: Mapping[str, Any], *, require_payload: bool = True) -> ContractCheckResult:
    """Validate a serialized websocket envelope against the public contract."""
    if not isinstance(payload, Mapping):
        return ContractCheckResult(False, 'envelope must be a mapping')
    required = ('eventId', 'type', 'ts', 'source', 'sessionId', 'seq', 'protocolVersion', 'schemaVersion')
    missing = [key for key in required if key not in payload]
    if missing:
        return ContractCheckResult(False, f'missing keys: {", ".join(missing)}')
    if require_payload and 'payload' not in payload:
        return ContractCheckResult(False, 'missing keys: payload')
    if str(payload.get('protocolVersion')) != PROTOCOL_VERSION:
        return ContractCheckResult(False, f'protocol version mismatch: {payload.get("protocolVersion")}')
    if str(payload.get('schemaVersion')) != SCHEMA_VERSION:
        return ContractCheckResult(False, f'schema version mismatch: {payload.get("schemaVersion")}')
    event_type = str(payload.get('type', ''))
    if not event_type:
        return ContractCheckResult(False, 'event type must be non-empty')
    if 'payload' in payload and not isinstance(payload.get('payload'), Mapping):
        return ContractCheckResult(False, 'payload must be an object')
    try:
        if int(payload.get('seq', -1)) < 0:
            return ContractCheckResult(False, 'seq must be a non-negative integer')
    except (TypeError, ValueError):
        return ContractCheckResult(False, 'seq must be a non-negative integer')
    capabilities = payload.get('capabilities')
    if capabilities is not None and not isinstance(capabilities, list):
        return ContractCheckResult(False, 'capabilities must be a list when present')
    compatibility_mode = payload.get('compatibilityMode')
    if compatibility_mode is not None and str(compatibility_mode) not in COMPATIBILITY_MODES:
        return ContractCheckResult(False, f'unsupported compatibility mode: {compatibility_mode}')
    return ContractCheckResult(True, 'ok')



def validate_outbound_command_type(command_type: str) -> ContractCheckResult:
    """Validate that one outbound command type is supported."""
    value = str(command_type or '').strip()
    if value not in COMMAND_TYPES:
        return ContractCheckResult(False, f'unsupported command type: {value}')
    return ContractCheckResult(True, 'ok')



def contract_version_snapshot() -> dict[str, object]:
    """Return a full contract snapshot used by audits and reports."""
    return {
        **CONTRACT_VERSIONS,
        'compatibility_modes': list(COMPATIBILITY_MODES),
        'capabilities': list(BRIDGE_CAPABILITIES),
        'command_types': list(COMMAND_TYPES),
        'command_ack_statuses': list(COMMAND_ACK_STATUSES),
        'command_lifecycle_statuses': list(COMMAND_LIFECYCLE_STATUSES),
        'transport_summary_keys': list(TRANSPORT_SUMMARY_KEYS),
        'command_permission_matrix': {key: list(value) for key, value in COMMAND_PERMISSION_MATRIX.items()},
        'runtime_param_keys': list(RUNTIME_PARAM_SCHEMA.keys()),
        'runtime_param_profiles': list(RUNTIME_PARAM_PROFILES.keys()),
    }
