from geometry_msgs.msg import Twist
from robot_control.arbiter import select_command
from robot_control.control_state import TimedTwist
from robot_utils.constants import MODE_MANUAL, MODE_PATROL
from robot_utils.helpers import monotonic_time


def make_cmd(vx: float):
    t = Twist()
    t.linear.x = vx
    return t


def test_manual_selected_when_fresh():
    timed = TimedTwist(cmd=make_cmd(0.2), stamp=monotonic_time(), valid=True)
    source, cmd = select_command(MODE_MANUAL, timed, TimedTwist(), TimedTwist(), TimedTwist(), 0.5)
    assert source == 'manual'
    assert cmd.linear.x == 0.2


def test_patrol_prefers_navigation_when_fresh():
    now = monotonic_time()
    source, cmd = select_command(
        MODE_PATROL,
        TimedTwist(),
        TimedTwist(cmd=make_cmd(0.1), stamp=now, valid=True),
        TimedTwist(),
        TimedTwist(cmd=make_cmd(0.3), stamp=now, valid=True),
        0.5,
    )
    assert source == 'navigation'
    assert cmd.linear.x == 0.3
