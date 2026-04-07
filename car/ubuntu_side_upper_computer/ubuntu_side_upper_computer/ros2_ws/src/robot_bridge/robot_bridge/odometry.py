from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin


@dataclass
class OdomState:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0


def integrate_odometry(state: OdomState, *, linear_velocity: float, angular_velocity: float, dt: float) -> OdomState:
    if dt <= 0.0:
        return OdomState(state.x, state.y, state.yaw)
    heading = state.yaw + angular_velocity * 0.5 * dt
    return OdomState(
        x=state.x + linear_velocity * cos(heading) * dt,
        y=state.y + linear_velocity * sin(heading) * dt,
        yaw=state.yaw + angular_velocity * dt,
    )


def yaw_to_quaternion(yaw: float) -> tuple[float, float, float, float]:
    from math import cos, sin
    half = yaw * 0.5
    return 0.0, 0.0, sin(half), cos(half)
