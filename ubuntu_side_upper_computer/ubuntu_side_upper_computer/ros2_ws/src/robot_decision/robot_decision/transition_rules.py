from __future__ import annotations

from robot_decision.mode_table import allowed_targets, get_mode_spec, transition_rows


def can_transition(current_mode: str, requested_mode: str) -> bool:
    return requested_mode in allowed_targets(current_mode)


def allowed_transitions(current_mode: str) -> set[str]:
    return set(allowed_targets(current_mode))


def explain_transition(current_mode: str, requested_mode: str) -> str:
    if can_transition(current_mode, requested_mode):
        return 'ok'
    allowed = ', '.join(sorted(allowed_transitions(current_mode))) or 'none'
    return f'transition {current_mode}->{requested_mode} not allowed; allowed: {allowed}'


def transition_table() -> tuple[dict[str, object], ...]:
    return transition_rows()


def transition_requires_manual_ack(current_mode: str) -> bool:
    return bool(get_mode_spec(current_mode).requires_manual_ack)
