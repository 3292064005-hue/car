from __future__ import annotations

from dataclasses import dataclass

from robot_utils.constants import MODE_BOOT, MODE_FAULT, MODE_IDLE, MODE_MANUAL, MODE_PATROL, MODE_SAFE_STOP, MODE_TRACK


@dataclass(frozen=True)
class ModeSpec:
    name: str
    allowed_targets: tuple[str, ...]
    requires_link_ok: bool = False
    requires_manual_ack: bool = False
    locks_motion: bool = False


MODE_TABLE: dict[str, ModeSpec] = {
    MODE_BOOT: ModeSpec(MODE_BOOT, (MODE_IDLE, MODE_FAULT), locks_motion=True),
    MODE_IDLE: ModeSpec(MODE_IDLE, (MODE_MANUAL, MODE_PATROL, MODE_SAFE_STOP, MODE_FAULT)),
    MODE_MANUAL: ModeSpec(MODE_MANUAL, (MODE_IDLE, MODE_SAFE_STOP, MODE_FAULT)),
    MODE_PATROL: ModeSpec(MODE_PATROL, (MODE_IDLE, MODE_MANUAL, MODE_TRACK, MODE_SAFE_STOP, MODE_FAULT), requires_link_ok=True),
    MODE_TRACK: ModeSpec(MODE_TRACK, (MODE_PATROL, MODE_IDLE, MODE_MANUAL, MODE_SAFE_STOP, MODE_FAULT), requires_link_ok=True),
    MODE_SAFE_STOP: ModeSpec(MODE_SAFE_STOP, (MODE_IDLE, MODE_MANUAL, MODE_FAULT), requires_link_ok=True, requires_manual_ack=True, locks_motion=True),
    MODE_FAULT: ModeSpec(MODE_FAULT, (MODE_IDLE,), locks_motion=True),
}


def get_mode_spec(mode: str) -> ModeSpec:
    return MODE_TABLE.get(mode, MODE_TABLE[MODE_IDLE])


def allowed_targets(mode: str) -> tuple[str, ...]:
    return get_mode_spec(mode).allowed_targets


def transition_rows() -> tuple[dict[str, object], ...]:
    rows = []
    for name, spec in MODE_TABLE.items():
        rows.append({
            'mode': name,
            'allowed_targets': list(spec.allowed_targets),
            'requires_link_ok': spec.requires_link_ok,
            'requires_manual_ack': spec.requires_manual_ack,
            'locks_motion': spec.locks_motion,
        })
    return tuple(rows)
