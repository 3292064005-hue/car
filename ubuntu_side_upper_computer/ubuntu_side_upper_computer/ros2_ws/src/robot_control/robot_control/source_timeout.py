from __future__ import annotations

from robot_control.control_state import TimedTwist
from robot_utils.helpers import monotonic_time


def source_age_sec(source: TimedTwist) -> float:
    if not source.valid:
        return float('inf')
    return monotonic_time() - source.stamp


def is_fresh(source: TimedTwist, timeout_sec: float) -> bool:
    if not source.valid:
        return False
    return source_age_sec(source) <= timeout_sec
