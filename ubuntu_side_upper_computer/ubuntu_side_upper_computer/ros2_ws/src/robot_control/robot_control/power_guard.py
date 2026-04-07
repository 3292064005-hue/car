from typing import Any
from geometry_msgs.msg import Twist


def apply_power_guard(
    cmd: Twist,
    power_state: Any | None,
    low_power_linear_scale: float,
    low_power_angular_scale: float = 0.8,
    critical_zero: bool = True,
    include_reason: bool = False,
    power_state_stale: bool = False,
):
    """Apply low-power and stale-telemetry motion limiting.

    Args:
        cmd: Requested chassis command.
        power_state: Latest power telemetry object or ``None``.
        low_power_linear_scale: Scaling factor applied on low-power warning.
        low_power_angular_scale: Angular scaling factor applied on low-power warning.
        critical_zero: Whether critical-stop states should hard-zero the command.
        include_reason: Whether to also return the applied reason string.
        power_state_stale: Whether the power telemetry age exceeded its timeout budget.

    Returns:
        ``(Twist, limited)`` or ``(Twist, limited, reason)`` when ``include_reason`` is enabled.

    Raises:
        None.
    """
    out = Twist()
    out.linear.x = cmd.linear.x
    out.angular.z = cmd.angular.z
    limited = False
    reason = 'normal'
    if power_state_stale and critical_zero:
        out.linear.x = 0.0
        out.angular.z = 0.0
        limited = True
        reason = 'power_state_stale'
    elif power_state is not None:
        if getattr(power_state, 'low_power_stop', False) and critical_zero:
            out.linear.x = 0.0
            out.angular.z = 0.0
            limited = True
            reason = 'critical_stop'
        elif getattr(power_state, 'low_power_warn', False):
            out.linear.x *= low_power_linear_scale
            out.angular.z *= low_power_angular_scale
            limited = True
            reason = 'warn_scale'
    if include_reason:
        return out, limited, reason
    return out, limited
