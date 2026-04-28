from __future__ import annotations

from geometry_msgs.msg import Twist
from robot_msgs.msg import ChassisState, Fault
from robot_utils.constants import (
    FAULT_COMM_LOSS,
    FAULT_ESTOP,
    FAULT_LEVEL_ERROR,
    FAULT_LEVEL_FATAL,
    FAULT_MOTOR,
    FAULT_PROTOCOL,
    MODE_FAULT,
    MODE_SAFE_STOP,
)

BLOCKING_FAULT_CODES = {
    FAULT_COMM_LOSS,
    FAULT_ESTOP,
    FAULT_MOTOR,
    FAULT_PROTOCOL,
}


def apply_safety(
    cmd: Twist,
    mode: str,
    chassis_state: ChassisState | None,
    fault: Fault | None,
    *,
    chassis_state_stale: bool = False,
    fault_hold_active: bool = False,
    include_reason: bool = False,
):
    out = Twist()
    out.linear.x = cmd.linear.x
    out.angular.z = cmd.angular.z
    latched = False
    reason = 'normal'

    if mode in {MODE_SAFE_STOP, MODE_FAULT}:
        out.linear.x = 0.0
        out.angular.z = 0.0
        latched = True
        reason = 'mode_blocked'
    elif fault_hold_active:
        out.linear.x = 0.0
        out.angular.z = 0.0
        latched = True
        reason = 'fault_hold'
    elif chassis_state_stale:
        out.linear.x = 0.0
        out.angular.z = 0.0
        latched = True
        reason = 'chassis_state_stale'
    elif chassis_state is not None and bool(getattr(chassis_state, 'estop', False)):
        out.linear.x = 0.0
        out.angular.z = 0.0
        latched = True
        reason = 'estop'
    elif chassis_state is not None and not bool(getattr(chassis_state, 'comm_ok', True)):
        out.linear.x = 0.0
        out.angular.z = 0.0
        latched = True
        reason = 'chassis_comm_lost'
    elif chassis_state is not None and not bool(getattr(chassis_state, 'heartbeat_ok', True)):
        out.linear.x = 0.0
        out.angular.z = 0.0
        latched = True
        reason = 'chassis_heartbeat_lost'
    elif fault is not None and getattr(fault, 'level', None) in {FAULT_LEVEL_ERROR, FAULT_LEVEL_FATAL}:
        out.linear.x = 0.0
        out.angular.z = 0.0
        latched = True
        reason = f'fault_level:{getattr(fault, "code", None) or "unknown"}'
    elif fault is not None and getattr(fault, 'code', None) in BLOCKING_FAULT_CODES:
        out.linear.x = 0.0
        out.angular.z = 0.0
        latched = True
        reason = f'blocking_fault:{getattr(fault, "code", "unknown")}'

    if include_reason:
        return out, latched, reason
    return out, latched
