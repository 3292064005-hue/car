from __future__ import annotations

from robot_msgs.msg import VisionTarget
from robot_utils.constants import MODE_FAULT, MODE_PATROL, MODE_SAFE_STOP, MODE_TRACK


def should_enter_track(current_mode: str, target: VisionTarget | None, auto_track_enabled: bool, min_confidence: float) -> bool:
    if not auto_track_enabled or current_mode != MODE_PATROL or target is None:
        return False
    return bool(target.detected and target.confidence >= min_confidence)


def should_exit_track(target: VisionTarget | None, lost_count: int, lost_limit: int) -> bool:
    if target is not None and target.detected:
        return False
    return lost_count >= lost_limit


def allows_snapshot(current_mode: str) -> bool:
    return current_mode not in {MODE_SAFE_STOP, MODE_FAULT}


def track_fallback_mode(patrol_started: bool, patrol_completed: bool) -> str:
    return MODE_PATROL if patrol_started and not patrol_completed else 'IDLE'
