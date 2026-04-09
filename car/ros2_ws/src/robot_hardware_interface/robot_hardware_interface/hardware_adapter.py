from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class JointStateSnapshot:
    """Integrated wheel state for standard JointState publication.

    Attributes:
        left_position_rad: Integrated left-wheel angle.
        right_position_rad: Integrated right-wheel angle.
        left_velocity_rad_s: Left-wheel angular velocity.
        right_velocity_rad_s: Right-wheel angular velocity.
    """

    left_position_rad: float
    right_position_rad: float
    left_velocity_rad_s: float
    right_velocity_rad_s: float


class WheelDriveEstimator:
    """Integrate wheel feedback from differential-drive RPM telemetry.

    The estimator is intentionally stateful because wheel position must be integrated
    across callbacks while keeping the node logic small and deterministic.
    """

    def __init__(self) -> None:
        self._left_position_rad = 0.0
        self._right_position_rad = 0.0

    def update(self, *, left_rpm: float, right_rpm: float, dt_sec: float) -> JointStateSnapshot:
        """Advance wheel positions using one feedback sample.

        Args:
            left_rpm: Left-wheel speed in RPM.
            right_rpm: Right-wheel speed in RPM.
            dt_sec: Integration interval in seconds.

        Returns:
            Integrated wheel-state snapshot.

        Raises:
            ValueError: If ``dt_sec`` is negative.
        """
        if dt_sec < 0.0:
            raise ValueError('dt_sec must be >= 0')
        left_velocity = float(left_rpm) * 2.0 * math.pi / 60.0
        right_velocity = float(right_rpm) * 2.0 * math.pi / 60.0
        self._left_position_rad += left_velocity * dt_sec
        self._right_position_rad += right_velocity * dt_sec
        return JointStateSnapshot(
            left_position_rad=self._left_position_rad,
            right_position_rad=self._right_position_rad,
            left_velocity_rad_s=left_velocity,
            right_velocity_rad_s=right_velocity,
        )
