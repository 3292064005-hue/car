from geometry_msgs.msg import Twist
from robot_utils.helpers import clamp


def limit_twist(
    cmd: Twist,
    max_linear: float,
    max_angular: float,
    reverse_max_linear: float | None = None,
    turn_slowdown_ratio: float = 0.0,
    track_linear_scale: float = 1.0,
    track_angular_scale: float = 1.0,
    mode: str | None = None,
) -> Twist:
    out = Twist()
    rev_cap = abs(reverse_max_linear) if reverse_max_linear is not None else max_linear
    linear_cap = max_linear
    angular_cap = max_angular
    if mode == 'TRACK':
        linear_cap *= track_linear_scale
        angular_cap *= track_angular_scale
        rev_cap = min(rev_cap, linear_cap)
    out.linear.x = clamp(cmd.linear.x, -rev_cap, linear_cap)
    out.angular.z = clamp(cmd.angular.z, -angular_cap, angular_cap)
    if turn_slowdown_ratio > 0.0 and angular_cap > 0.0:
        turn_ratio = min(abs(out.angular.z) / angular_cap, 1.0)
        dynamic_cap = linear_cap * (1.0 - turn_slowdown_ratio * turn_ratio)
        if out.linear.x >= 0.0:
            out.linear.x = clamp(out.linear.x, -rev_cap, dynamic_cap)
    return out
