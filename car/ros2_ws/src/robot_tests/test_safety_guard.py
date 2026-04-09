from robot_control.safety_guard import apply_safety
from geometry_msgs.msg import Twist
from robot_msgs.msg import ChassisState, Fault
from robot_utils.constants import MODE_MANUAL, FAULT_LEVEL_ERROR, FAULT_ESTOP


def test_apply_safety_reports_stale_reason():
    cmd = Twist()
    cmd.linear.x = 0.2
    out, latched, reason = apply_safety(cmd, MODE_MANUAL, None, None, chassis_state_stale=True, include_reason=True)
    assert latched is True
    assert reason == 'chassis_state_stale'
    assert out.linear.x == 0.0


def test_apply_safety_reports_fault_hold_reason():
    cmd = Twist()
    cmd.angular.z = 0.6
    out, latched, reason = apply_safety(cmd, MODE_MANUAL, ChassisState(), None, fault_hold_active=True, include_reason=True)
    assert latched is True
    assert reason == 'fault_hold'
    assert out.angular.z == 0.0


def test_apply_safety_blocks_fault_code():
    cmd = Twist()
    cmd.linear.x = 0.1
    fault = Fault(code=FAULT_ESTOP, level=FAULT_LEVEL_ERROR)
    out, latched, reason = apply_safety(cmd, MODE_MANUAL, ChassisState(), fault, include_reason=True)
    assert latched is True
    assert reason.startswith('fault_level:')
    assert out.linear.x == 0.0
