from types import SimpleNamespace
from geometry_msgs.msg import Twist
from robot_control.power_guard import apply_power_guard


def test_low_power_warn_scales_speed():
    cmd = Twist()
    cmd.linear.x = 0.2
    cmd.angular.z = 0.6
    power = SimpleNamespace(low_power_warn=True, low_power_stop=False)
    out, limited = apply_power_guard(cmd, power, 0.5, 0.5)
    assert limited
    assert out.linear.x == 0.1
    assert out.angular.z == 0.3


def test_low_power_stop_zeros_speed():
    cmd = Twist()
    cmd.linear.x = 0.2
    power = SimpleNamespace(low_power_warn=False, low_power_stop=True)
    out, limited = apply_power_guard(cmd, power, 0.5)
    assert limited
    assert out.linear.x == 0.0



def test_stale_power_state_zeros_speed():
    cmd = Twist()
    cmd.linear.x = 0.2
    cmd.angular.z = 0.4
    power = SimpleNamespace(low_power_warn=False, low_power_stop=False)
    out, limited, reason = apply_power_guard(cmd, power, 0.5, include_reason=True, power_state_stale=True)
    assert limited is True
    assert out.linear.x == 0.0
    assert out.angular.z == 0.0
    assert reason == "power_state_stale"
