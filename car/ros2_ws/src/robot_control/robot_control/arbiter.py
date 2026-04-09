from __future__ import annotations

from typing import Any

from geometry_msgs.msg import Twist
from robot_control.control_state import TimedTwist
from robot_control.source_timeout import is_fresh, source_age_sec
from robot_utils.constants import (
    CONTROL_SOURCE_IDLE,
    CONTROL_SOURCE_MANUAL,
    CONTROL_SOURCE_NAVIGATION,
    CONTROL_SOURCE_PATROL,
    CONTROL_SOURCE_TRACK,
    MODE_IDLE,
    MODE_MANUAL,
    MODE_PATROL,
    MODE_TRACK,
)


def zero_twist() -> Twist:
    msg = Twist()
    msg.linear.x = 0.0
    msg.angular.z = 0.0
    return msg


def _candidate_payload(*, name: str, holder: TimedTwist, timeout_sec: float, mode: str, mode_gate: set[str], selected: bool, fallback_reason: str) -> dict[str, Any]:
    age_sec = source_age_sec(holder)
    fresh = is_fresh(holder, timeout_sec)
    eligible = mode in mode_gate and fresh
    if not holder.valid:
        reason = 'no_sample'
    elif not fresh:
        reason = f'stale_timeout>{timeout_sec:.3f}s'
    elif mode not in mode_gate:
        reason = f'mode_{mode.lower()}_blocks_{name}'
    elif selected:
        reason = 'selected'
    else:
        reason = fallback_reason
    return {
        'source': name,
        'valid': bool(holder.valid),
        'fresh': bool(fresh),
        'eligible': bool(eligible),
        'ageSec': None if age_sec == float('inf') else round(float(age_sec), 4),
        'timeoutSec': round(float(timeout_sec), 4),
        'selected': bool(selected),
        'reason': reason,
    }


def _arbitration_audit(
    *,
    mode: str,
    manual_cmd: TimedTwist,
    patrol_cmd: TimedTwist,
    track_cmd: TimedTwist,
    navigation_cmd: TimedTwist,
    manual_timeout_sec: float,
    patrol_timeout_sec: float,
    track_timeout_sec: float,
    navigation_timeout_sec: float,
    winner: str,
) -> dict[str, Any]:
    priorities = {
        MODE_MANUAL: [CONTROL_SOURCE_MANUAL, CONTROL_SOURCE_IDLE],
        MODE_TRACK: [CONTROL_SOURCE_TRACK, CONTROL_SOURCE_IDLE],
        MODE_PATROL: [CONTROL_SOURCE_NAVIGATION, CONTROL_SOURCE_PATROL, CONTROL_SOURCE_IDLE],
        MODE_IDLE: [CONTROL_SOURCE_IDLE],
    }
    candidate_rows = [
        _candidate_payload(
            name=CONTROL_SOURCE_MANUAL,
            holder=manual_cmd,
            timeout_sec=manual_timeout_sec,
            mode=mode,
            mode_gate={MODE_MANUAL},
            selected=winner == CONTROL_SOURCE_MANUAL,
            fallback_reason='manual_not_selected_for_current_mode',
        ),
        _candidate_payload(
            name=CONTROL_SOURCE_TRACK,
            holder=track_cmd,
            timeout_sec=track_timeout_sec,
            mode=mode,
            mode_gate={MODE_TRACK},
            selected=winner == CONTROL_SOURCE_TRACK,
            fallback_reason='track_not_selected_for_current_mode',
        ),
        _candidate_payload(
            name=CONTROL_SOURCE_NAVIGATION,
            holder=navigation_cmd,
            timeout_sec=navigation_timeout_sec,
            mode=mode,
            mode_gate={MODE_PATROL},
            selected=winner == CONTROL_SOURCE_NAVIGATION,
            fallback_reason='legacy_patrol_fallback' if winner == CONTROL_SOURCE_PATROL else 'navigation_preferred_in_patrol',
        ),
        _candidate_payload(
            name=CONTROL_SOURCE_PATROL,
            holder=patrol_cmd,
            timeout_sec=patrol_timeout_sec,
            mode=mode,
            mode_gate={MODE_PATROL},
            selected=winner == CONTROL_SOURCE_PATROL,
            fallback_reason='navigation_authoritative_or_patrol_not_requested',
        ),
    ]
    return {
        'mode': mode,
        'winner': winner,
        'priority': priorities.get(mode, [CONTROL_SOURCE_IDLE]),
        'candidates': candidate_rows,
        'fallbackActive': winner in {CONTROL_SOURCE_PATROL, CONTROL_SOURCE_IDLE},
        'selectionPolicy': 'manual>idle | track>idle | patrol:navigation>legacy_patrol>idle',
    }


def select_command(
    mode: str,
    manual_cmd: TimedTwist,
    patrol_cmd: TimedTwist,
    track_cmd: TimedTwist,
    navigation_cmd: TimedTwist,
    manual_timeout_sec: float,
    patrol_timeout_sec: float | None = None,
    track_timeout_sec: float | None = None,
    navigation_timeout_sec: float | None = None,
) -> tuple[str, Twist]:
    """Select one authoritative motion command for the current mode.

    Args:
        mode: Current high-level robot mode.
        manual_cmd: Timed manual override command.
        patrol_cmd: Legacy patrol velocity command.
        track_cmd: Target-tracking velocity command.
        navigation_cmd: Navigation-generated patrol velocity command.
        manual_timeout_sec: Freshness timeout for manual commands.
        patrol_timeout_sec: Freshness timeout for legacy patrol commands.
        track_timeout_sec: Freshness timeout for tracking commands.
        navigation_timeout_sec: Freshness timeout for navigation commands.

    Returns:
        Tuple ``(source_name, twist)`` where ``source_name`` records the winning
        source and ``twist`` is the selected command.

    Raises:
        None.

    Boundary behavior:
        In ``MODE_PATROL`` navigation becomes the preferred business-mainline
        source. The legacy patrol velocity topic remains as an explicit fallback
        so historical compatibility paths do not break while the navigation-led
        mission chain becomes authoritative.
    """
    source, twist, _ = select_command_with_audit(
        mode,
        manual_cmd,
        patrol_cmd,
        track_cmd,
        navigation_cmd,
        manual_timeout_sec,
        patrol_timeout_sec=patrol_timeout_sec,
        track_timeout_sec=track_timeout_sec,
        navigation_timeout_sec=navigation_timeout_sec,
    )
    return source, twist


def select_command_with_audit(
    mode: str,
    manual_cmd: TimedTwist,
    patrol_cmd: TimedTwist,
    track_cmd: TimedTwist,
    navigation_cmd: TimedTwist,
    manual_timeout_sec: float,
    patrol_timeout_sec: float | None = None,
    track_timeout_sec: float | None = None,
    navigation_timeout_sec: float | None = None,
) -> tuple[str, Twist, dict[str, Any]]:
    """Select one command and emit a stable arbitration audit payload.

    Args:
        mode: Current high-level robot mode.
        manual_cmd: Timed manual override command.
        patrol_cmd: Legacy patrol velocity command.
        track_cmd: Target-tracking velocity command.
        navigation_cmd: Navigation-generated patrol velocity command.
        manual_timeout_sec: Freshness timeout for manual commands.
        patrol_timeout_sec: Freshness timeout for legacy patrol commands.
        track_timeout_sec: Freshness timeout for tracking commands.
        navigation_timeout_sec: Freshness timeout for navigation commands.

    Returns:
        Tuple ``(source_name, twist, audit)`` where ``audit`` captures winner,
        candidate freshness, and fallback reasons for all upstream velocity
        producers.

    Raises:
        None.
    """
    patrol_timeout_sec = manual_timeout_sec if patrol_timeout_sec is None else patrol_timeout_sec
    track_timeout_sec = manual_timeout_sec if track_timeout_sec is None else track_timeout_sec
    navigation_timeout_sec = patrol_timeout_sec if navigation_timeout_sec is None else navigation_timeout_sec
    winner = CONTROL_SOURCE_IDLE
    cmd = zero_twist()
    if mode == MODE_MANUAL and is_fresh(manual_cmd, manual_timeout_sec):
        winner = CONTROL_SOURCE_MANUAL
        cmd = manual_cmd.cmd
    elif mode == MODE_TRACK and is_fresh(track_cmd, track_timeout_sec):
        winner = CONTROL_SOURCE_TRACK
        cmd = track_cmd.cmd
    elif mode == MODE_PATROL:
        if is_fresh(navigation_cmd, navigation_timeout_sec):
            winner = CONTROL_SOURCE_NAVIGATION
            cmd = navigation_cmd.cmd
        elif is_fresh(patrol_cmd, patrol_timeout_sec):
            winner = CONTROL_SOURCE_PATROL
            cmd = patrol_cmd.cmd
    audit = _arbitration_audit(
        mode=mode,
        manual_cmd=manual_cmd,
        patrol_cmd=patrol_cmd,
        track_cmd=track_cmd,
        navigation_cmd=navigation_cmd,
        manual_timeout_sec=manual_timeout_sec,
        patrol_timeout_sec=patrol_timeout_sec,
        track_timeout_sec=track_timeout_sec,
        navigation_timeout_sec=navigation_timeout_sec,
        winner=winner,
    )
    return winner, cmd, audit
