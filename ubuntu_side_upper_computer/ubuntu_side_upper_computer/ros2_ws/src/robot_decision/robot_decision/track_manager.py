from __future__ import annotations

from typing import Any

from geometry_msgs.msg import Twist
from robot_utils.helpers import clamp


class TrackManager:
    def __init__(
        self,
        angular_kp: float = 1.4,
        linear_kp: float = 0.4,
        max_linear: float = 0.18,
        max_angular: float = 0.9,
        desired_area: float = 0.12,
        offset_deadband: float = 0.05,
        min_confidence: float = 0.55,
        lost_decay: float = 0.5,
    ) -> None:
        self.angular_kp = angular_kp
        self.linear_kp = linear_kp
        self.max_linear = max_linear
        self.max_angular = max_angular
        self.desired_area = desired_area
        self.offset_deadband = offset_deadband
        self.min_confidence = min_confidence
        self.lost_decay = lost_decay
        self.last_cmd = Twist()

    def compute_cmd(self, target: Any | None) -> Twist:
        cmd = Twist()
        if target is None or not getattr(target, 'detected', False) or getattr(target, 'confidence', 0.0) < self.min_confidence:
            cmd.linear.x = self.last_cmd.linear.x * self.lost_decay
            cmd.angular.z = self.last_cmd.angular.z * self.lost_decay
            self.last_cmd = cmd
            return cmd
        offset_x = getattr(target, 'offset_x', 0.0)
        area = getattr(target, 'area', 0.0)
        offset_x = 0.0 if abs(offset_x) < self.offset_deadband else offset_x
        cmd.angular.z = clamp(-offset_x * self.angular_kp, -self.max_angular, self.max_angular)
        linear = (self.desired_area - area) * self.linear_kp
        if abs(cmd.angular.z) > (0.6 * self.max_angular):
            linear *= 0.6
        cmd.linear.x = clamp(linear, -self.max_linear, self.max_linear)
        self.last_cmd = cmd
        return cmd
