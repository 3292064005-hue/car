from __future__ import annotations

"""Web bridge payload budgeting helpers shared by runtime and CI checks."""

import json
from typing import Any

CONTROL_EVENT_TYPES = frozenset({'command_ack', 'task_event', 'fault_event', 'mode_state', 'snapshot'})
DEFAULT_TELEMETRY_PAYLOAD_BUDGET_BYTES = 64 * 1024
DEFAULT_CONTROL_PAYLOAD_BUDGET_BYTES = 128 * 1024
DEFAULT_SNAPSHOT_PAYLOAD_BUDGET_BYTES = 256 * 1024


def resolve_payload_budget(
    event_type: str,
    *,
    telemetry_budget_bytes: int = DEFAULT_TELEMETRY_PAYLOAD_BUDGET_BYTES,
    control_budget_bytes: int = DEFAULT_CONTROL_PAYLOAD_BUDGET_BYTES,
    snapshot_budget_bytes: int = DEFAULT_SNAPSHOT_PAYLOAD_BUDGET_BYTES,
) -> tuple[str, int]:
    """Return the logical lane label and byte budget for one envelope type.

    Args:
        event_type: Envelope type.
        telemetry_budget_bytes: Runtime telemetry payload budget.
        control_budget_bytes: Runtime control payload budget.
        snapshot_budget_bytes: Runtime snapshot payload budget.

    Returns:
        ``(lane, budget_bytes)`` for the supplied event type.

    Raises:
        None.
    """
    if event_type == 'snapshot':
        return 'snapshot', int(snapshot_budget_bytes)
    if event_type in CONTROL_EVENT_TYPES:
        return 'control', int(control_budget_bytes)
    return 'telemetry', int(telemetry_budget_bytes)



def envelope_size_bytes(envelope: dict[str, Any]) -> int:
    """Return UTF-8 encoded envelope size in bytes."""
    return len(json.dumps(envelope, ensure_ascii=False).encode('utf-8'))
