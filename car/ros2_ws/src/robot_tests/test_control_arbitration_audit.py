from geometry_msgs.msg import Twist
from robot_control.arbiter import select_command_with_audit
from robot_control.control_state import TimedTwist
from robot_utils.constants import MODE_PATROL
from robot_utils.helpers import monotonic_time


def make_cmd(vx: float):
    t = Twist()
    t.linear.x = vx
    return t


def test_patrol_arbitration_audit_explains_legacy_fallback() -> None:
    now = monotonic_time()
    winner, cmd, audit = select_command_with_audit(
        MODE_PATROL,
        TimedTwist(),
        TimedTwist(cmd=make_cmd(0.1), stamp=now, valid=True),
        TimedTwist(),
        TimedTwist(cmd=make_cmd(0.3), stamp=now - 10.0, valid=True),
        0.5,
    )
    assert winner == 'patrol'
    assert cmd.linear.x == 0.1
    assert audit['winner'] == 'patrol'
    nav_row = next(item for item in audit['candidates'] if item['source'] == 'navigation')
    patrol_row = next(item for item in audit['candidates'] if item['source'] == 'patrol')
    assert nav_row['reason'].startswith('stale_timeout')
    assert patrol_row['selected'] is True
