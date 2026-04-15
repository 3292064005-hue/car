from __future__ import annotations

"""Decision-side mode view derived from the authoritative mode catalog."""

from dataclasses import dataclass

from robot_utils.mode_catalog import get_mode_catalog_entry, mode_transition_rows


@dataclass(frozen=True)
class ModeSpec:
    """Decision-side immutable view of one mode specification."""

    name: str
    allowed_targets: tuple[str, ...]
    requires_link_ok: bool = False
    requires_manual_ack: bool = False
    locks_motion: bool = False


MODE_TABLE: dict[str, ModeSpec] = {
    row['mode']: ModeSpec(
        name=str(row['mode']),
        allowed_targets=tuple(str(item) for item in row['allowed_targets']),
        requires_link_ok=bool(row['requires_link_ok']),
        requires_manual_ack=bool(row['requires_manual_ack']),
        locks_motion=bool(row['locks_motion']),
    )
    for row in mode_transition_rows()
}


def get_mode_spec(mode: str) -> ModeSpec:
    entry = get_mode_catalog_entry(mode)
    return MODE_TABLE[entry.name]


def allowed_targets(mode: str) -> tuple[str, ...]:
    return get_mode_spec(mode).allowed_targets


def transition_rows() -> tuple[dict[str, object], ...]:
    return mode_transition_rows()
