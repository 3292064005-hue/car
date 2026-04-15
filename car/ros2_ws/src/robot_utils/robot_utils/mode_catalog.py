from __future__ import annotations

"""Authoritative robot mode catalog shared across backend, contracts, reports, and UI fallbacks.

This module is the single facts source for robot mode identifiers, priorities,
transition reachability, and mode-level runtime constraints. Downstream modules
must derive their local artifacts from this catalog instead of re-declaring
parallel transition tables.
"""

from dataclasses import dataclass
from typing import Any

MODE_BOOT = 'BOOT'
MODE_IDLE = 'IDLE'
MODE_MANUAL = 'MANUAL'
MODE_PATROL = 'PATROL'
MODE_TRACK = 'TRACK'
MODE_SAFE_STOP = 'SAFE_STOP'
MODE_FAULT = 'FAULT'

MODE_SEQUENCE: tuple[str, ...] = (
    MODE_BOOT,
    MODE_IDLE,
    MODE_MANUAL,
    MODE_PATROL,
    MODE_TRACK,
    MODE_SAFE_STOP,
    MODE_FAULT,
)

MODE_PRIORITY: dict[str, int] = {
    MODE_FAULT: 100,
    MODE_SAFE_STOP: 90,
    MODE_MANUAL: 80,
    MODE_TRACK: 70,
    MODE_PATROL: 60,
    MODE_IDLE: 10,
    MODE_BOOT: 0,
}


@dataclass(frozen=True, slots=True)
class ModeCatalogEntry:
    """One authoritative mode specification.

    Args:
        name: Canonical mode identifier exposed across backend/frontend contracts.
        allowed_targets: Authoritative target modes reachable from ``name``.
        requires_link_ok: Whether runtime link health must be nominal before entering/holding the mode.
        requires_manual_ack: Whether leaving SAFE_STOP requires explicit operator acknowledgement.
        locks_motion: Whether the mode must lock motion outputs.

    Returns:
        Immutable mode catalog entry.

    Raises:
        None.

    Boundary behavior:
        ``allowed_targets`` is normalized to a tuple and must remain free of duplicates so
        generated artifacts stay deterministic.
    """

    name: str
    allowed_targets: tuple[str, ...]
    requires_link_ok: bool = False
    requires_manual_ack: bool = False
    locks_motion: bool = False


MODE_CATALOG: dict[str, ModeCatalogEntry] = {
    MODE_BOOT: ModeCatalogEntry(MODE_BOOT, (MODE_IDLE, MODE_FAULT), locks_motion=True),
    MODE_IDLE: ModeCatalogEntry(MODE_IDLE, (MODE_MANUAL, MODE_PATROL, MODE_SAFE_STOP, MODE_FAULT)),
    MODE_MANUAL: ModeCatalogEntry(MODE_MANUAL, (MODE_IDLE, MODE_SAFE_STOP, MODE_FAULT)),
    MODE_PATROL: ModeCatalogEntry(MODE_PATROL, (MODE_IDLE, MODE_MANUAL, MODE_TRACK, MODE_SAFE_STOP, MODE_FAULT), requires_link_ok=True),
    MODE_TRACK: ModeCatalogEntry(MODE_TRACK, (MODE_PATROL, MODE_IDLE, MODE_MANUAL, MODE_SAFE_STOP, MODE_FAULT), requires_link_ok=True),
    MODE_SAFE_STOP: ModeCatalogEntry(MODE_SAFE_STOP, (MODE_IDLE, MODE_MANUAL, MODE_FAULT), requires_link_ok=True, requires_manual_ack=True, locks_motion=True),
    MODE_FAULT: ModeCatalogEntry(MODE_FAULT, (MODE_IDLE,), locks_motion=True),
}

MODE_TRANSITION_TARGETS: dict[str, tuple[str, ...]] = {
    name: entry.allowed_targets for name, entry in MODE_CATALOG.items()
}


def get_mode_catalog_entry(mode: str) -> ModeCatalogEntry:
    """Return the authoritative mode entry for one requested mode.

    Args:
        mode: Requested mode identifier.

    Returns:
        Matching authoritative entry, or the IDLE entry when the input is unknown.

    Raises:
        None.

    Boundary behavior:
        Unknown/empty modes fall back to ``IDLE`` so callers keep deterministic read-side
        behavior instead of crashing while still converging to a safe default.
    """

    return MODE_CATALOG.get(str(mode or '').strip().upper(), MODE_CATALOG[MODE_IDLE])


def allowed_targets_for_mode(mode: str) -> tuple[str, ...]:
    """Return authoritative target modes for one current mode."""
    return get_mode_catalog_entry(mode).allowed_targets


def mode_transition_rows() -> tuple[dict[str, Any], ...]:
    """Render deterministic rows for reports and generated artifacts."""
    rows: list[dict[str, Any]] = []
    for name in MODE_SEQUENCE:
        entry = MODE_CATALOG[name]
        rows.append({
            'mode': name,
            'allowed_targets': list(entry.allowed_targets),
            'requires_link_ok': entry.requires_link_ok,
            'requires_manual_ack': entry.requires_manual_ack,
            'locks_motion': entry.locks_motion,
            'priority': MODE_PRIORITY[name],
        })
    return tuple(rows)


__all__ = [
    'MODE_BOOT', 'MODE_IDLE', 'MODE_MANUAL', 'MODE_PATROL', 'MODE_TRACK', 'MODE_SAFE_STOP', 'MODE_FAULT',
    'MODE_SEQUENCE', 'MODE_PRIORITY', 'MODE_CATALOG', 'MODE_TRANSITION_TARGETS', 'ModeCatalogEntry',
    'allowed_targets_for_mode', 'get_mode_catalog_entry', 'mode_transition_rows',
]
