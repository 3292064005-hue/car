from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Pose2D:
    """Simple planar pose used by the odometry integrator.

    Attributes:
        x: X position in meters.
        y: Y position in meters.
        yaw: Heading in radians.
    """

    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0


def normalize_angle(angle_rad: float) -> float:
    """Normalize one angle into ``[-pi, pi]``.

    Args:
        angle_rad: Raw angle in radians.

    Returns:
        Wrapped angle in radians.

    Raises:
        None.
    """
    return math.atan2(math.sin(angle_rad), math.cos(angle_rad))


def integrate_pose(*, pose: Pose2D, linear_velocity_m_s: float, angular_velocity_rad_s: float, dt_sec: float) -> Pose2D:
    """Integrate one planar differential-drive motion step.

    Args:
        pose: Previous pose estimate.
        linear_velocity_m_s: Forward velocity.
        angular_velocity_rad_s: Yaw rate.
        dt_sec: Time step in seconds.

    Returns:
        Updated pose.

    Raises:
        ValueError: If ``dt_sec`` is negative.
    """
    if dt_sec < 0.0:
        raise ValueError('dt_sec must be >= 0')
    if dt_sec == 0.0:
        return pose
    mid_yaw = pose.yaw + angular_velocity_rad_s * dt_sec * 0.5
    dx = linear_velocity_m_s * math.cos(mid_yaw) * dt_sec
    dy = linear_velocity_m_s * math.sin(mid_yaw) * dt_sec
    return Pose2D(
        x=pose.x + dx,
        y=pose.y + dy,
        yaw=normalize_angle(pose.yaw + angular_velocity_rad_s * dt_sec),
    )


def yaw_to_quaternion(yaw: float) -> tuple[float, float, float, float]:
    """Convert one planar yaw into a quaternion tuple.

    Args:
        yaw: Heading in radians.

    Returns:
        Quaternion tuple in ``(x, y, z, w)`` order.

    Raises:
        None.
    """
    half = yaw * 0.5
    return (0.0, 0.0, math.sin(half), math.cos(half))
