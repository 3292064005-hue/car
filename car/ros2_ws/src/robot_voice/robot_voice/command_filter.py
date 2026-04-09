from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass
class CommandFilterState:
    last_command: str = ''
    last_time: float = 0.0
    per_command_time: dict[str, float] = field(default_factory=dict)


def accept_with_reason(command: str, state: CommandFilterState, debounce_sec: float, per_command_cooldown_sec: float | None = None, *, confidence: float | None = None, min_confidence: float = 0.0) -> tuple[bool, str]:
    now = time.monotonic()
    if confidence is not None and confidence < min_confidence:
        return False, 'low_confidence'
    if command == state.last_command and (now - state.last_time) < debounce_sec:
        return False, 'debounced'
    if per_command_cooldown_sec is not None:
        last = state.per_command_time.get(command, 0.0)
        if (now - last) < per_command_cooldown_sec:
            return False, 'command_cooldown'
        state.per_command_time[command] = now
    state.last_command = command
    state.last_time = now
    return True, 'accepted'


def should_accept(command: str, state: CommandFilterState, debounce_sec: float, per_command_cooldown_sec: float | None = None) -> bool:
    accepted, _reason = accept_with_reason(command, state, debounce_sec, per_command_cooldown_sec)
    return accepted
