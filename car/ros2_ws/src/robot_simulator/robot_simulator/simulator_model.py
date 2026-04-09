from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class DifferentialDriveState:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0
    battery_percent: float = 100.0
    battery_voltage: float = 12.6


def step_simulation(*, state: DifferentialDriveState, linear_cmd: float, angular_cmd: float, dt_sec: float, moving_drain_per_sec: float, idle_drain_per_sec: float) -> DifferentialDriveState:
    """Advance a minimal differential-drive simulator.

    Args:
        state: Current simulator state.
        linear_cmd: Commanded linear velocity.
        angular_cmd: Commanded angular velocity.
        dt_sec: Time step in seconds.
        moving_drain_per_sec: Battery drain rate while moving.
        idle_drain_per_sec: Battery drain rate while idle.

    Returns:
        Updated simulator state.

    Raises:
        ValueError: If ``dt_sec`` is negative.
    """
    if dt_sec < 0.0:
        raise ValueError('dt_sec must be >= 0')
    if dt_sec == 0.0:
        return state
    import math
    next_yaw = state.yaw + angular_cmd * dt_sec
    next_x = state.x + linear_cmd * math.cos(next_yaw) * dt_sec
    next_y = state.y + linear_cmd * math.sin(next_yaw) * dt_sec
    drain = moving_drain_per_sec if abs(linear_cmd) > 1e-6 or abs(angular_cmd) > 1e-6 else idle_drain_per_sec
    next_percent = max(0.0, state.battery_percent - drain * dt_sec)
    next_voltage = 11.0 + 1.6 * (next_percent / 100.0)
    return DifferentialDriveState(
        x=next_x,
        y=next_y,
        yaw=next_yaw,
        linear_velocity=linear_cmd,
        angular_velocity=angular_cmd,
        battery_percent=next_percent,
        battery_voltage=next_voltage,
    )
