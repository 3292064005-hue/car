from __future__ import annotations

from geometry_msgs.msg import Twist
from robot_control.control_state import TimedTwist
from robot_control.source_timeout import is_fresh
from robot_utils.constants import (
    CONTROL_SOURCE_IDLE,
    CONTROL_SOURCE_MANUAL,
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


def select_command(
    mode: str,
    manual_cmd: TimedTwist,
    patrol_cmd: TimedTwist,
    track_cmd: TimedTwist,
    manual_timeout_sec: float,
    patrol_timeout_sec: float | None = None,
    track_timeout_sec: float | None = None,
) -> tuple[str, Twist]:
    patrol_timeout_sec = manual_timeout_sec if patrol_timeout_sec is None else patrol_timeout_sec
    track_timeout_sec = manual_timeout_sec if track_timeout_sec is None else track_timeout_sec
    if mode == MODE_MANUAL and is_fresh(manual_cmd, manual_timeout_sec):
        return CONTROL_SOURCE_MANUAL, manual_cmd.cmd
    if mode == MODE_TRACK and is_fresh(track_cmd, track_timeout_sec):
        return CONTROL_SOURCE_TRACK, track_cmd.cmd
    if mode == MODE_PATROL and is_fresh(patrol_cmd, patrol_timeout_sec):
        return CONTROL_SOURCE_PATROL, patrol_cmd.cmd
    if mode == MODE_IDLE:
        return CONTROL_SOURCE_IDLE, zero_twist()
    return CONTROL_SOURCE_IDLE, zero_twist()
