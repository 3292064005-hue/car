from geometry_msgs.msg import Twist
from robot_utils.helpers import step_towards


def apply_ramp(previous: Twist, target: Twist, max_linear_step: float, max_angular_step: float) -> Twist:
    out = Twist()
    out.linear.x = step_towards(previous.linear.x, target.linear.x, max_linear_step)
    out.angular.z = step_towards(previous.angular.z, target.angular.z, max_angular_step)
    return out
