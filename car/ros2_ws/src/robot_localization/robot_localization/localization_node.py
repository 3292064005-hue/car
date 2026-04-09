from __future__ import annotations

import json
from typing import Sequence

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String

from robot_description.description_model import load_description_model
from robot_msgs.msg import ChassisState
from robot_utils.helpers import monotonic_time, safe_json_dumps
from robot_utils.qos_profiles import qos_for
from .localization_math import Pose2D, integrate_pose, yaw_to_quaternion

try:
    from geometry_msgs.msg import TransformStamped
    from tf2_ros import TransformBroadcaster
except Exception:  # pragma: no cover - lightweight test stubs may omit tf2_ros
    TransformStamped = None
    TransformBroadcaster = None


class RobotLocalizationNode(Node):
    """Fuse chassis telemetry into a ROS-native odometry estimate.

    The implementation is intentionally conservative: it integrates planar motion
    from the validated chassis telemetry, publishes odometry, and optionally
    publishes the matching odom->base_link transform.
    """

    def __init__(self) -> None:
        super().__init__('robot_localization')
        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('summary_topic', '/robot/localization/summary')
        self.declare_parameter('description_path', '')
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('max_dt_sec', 0.5)
        self.declare_parameter('velocity_timeout_sec', 0.8)
        self.declare_parameter('pose_covariance_diag', [0.02, 0.02, 0.02, 0.1, 0.1, 0.08])
        self.declare_parameter('twist_covariance_diag', [0.05, 0.05, 0.05, 0.1, 0.1, 0.12])

        self._pose = Pose2D()
        self._description_loaded = False
        self._description_robot_name = ''
        description_path = str(self.get_parameter('description_path').value or '').strip()
        if description_path:
            model = load_description_model(description_path)
            self._description_loaded = True
            self._description_robot_name = model.robot_name
            if str(self.get_parameter('odom_frame').value) == 'odom':
                self.set_parameters([rclpy.parameter.Parameter('odom_frame', value=model.frames.odom)])
            if str(self.get_parameter('base_frame').value) == 'base_link':
                self.set_parameters([rclpy.parameter.Parameter('base_frame', value=model.frames.base)])

        self._last_sample_at = monotonic_time()
        self._last_feedback_at = 0.0
        self._last_feedback: ChassisState | None = None
        self._last_linear = 0.0
        self._last_angular = 0.0

        self.odom_pub = self.create_publisher(Odometry, str(self.get_parameter('odom_topic').value), qos_for('telemetry'))
        self.summary_pub = self.create_publisher(String, str(self.get_parameter('summary_topic').value), qos_for('status_summary'))
        self.tf_broadcaster = TransformBroadcaster(self) if bool(self.get_parameter('publish_tf').value) and TransformBroadcaster is not None else None
        self.create_subscription(ChassisState, '/robot/chassis_state', self.on_chassis_state, qos_for('telemetry'))
        self.summary_timer = self.create_timer(0.5, self.publish_summary)

    def _diag_covariance(self, diag: Sequence[float]) -> list[float]:
        values = list(float(item) for item in diag)
        if len(values) != 6:
            raise ValueError('covariance diagonal must have exactly 6 entries')
        matrix = [0.0] * 36
        for index, value in enumerate(values):
            matrix[index * 6 + index] = value
        return matrix

    def on_chassis_state(self, msg: ChassisState) -> None:
        """Consume one chassis feedback sample and update the odometry estimate.

        Args:
            msg: Chassis telemetry containing linear and angular velocity.

        Returns:
            None.

        Raises:
            None. Invalid or stale feedback is converted into a safe zero-velocity update.
        """
        now = monotonic_time()
        raw_dt = max(0.0, now - self._last_sample_at)
        self._last_sample_at = now
        dt_sec = min(raw_dt, float(self.get_parameter('max_dt_sec').value))
        if not bool(msg.comm_ok) or bool(msg.estop) or not bool(msg.motor_enabled):
            linear = 0.0
            angular = 0.0
        else:
            linear = float(msg.linear_velocity)
            angular = float(msg.angular_velocity)
        self._pose = integrate_pose(pose=self._pose, linear_velocity_m_s=linear, angular_velocity_rad_s=angular, dt_sec=dt_sec)
        self._last_linear = linear
        self._last_angular = angular
        self._last_feedback = msg
        self._last_feedback_at = now
        self.publish_odometry()

    def publish_odometry(self) -> None:
        """Publish the current odometry and optional TF transform.

        Returns:
            None.

        Raises:
            None.
        """
        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = str(self.get_parameter('odom_frame').value)
        odom.child_frame_id = str(self.get_parameter('base_frame').value)
        odom.pose.pose.position.x = self._pose.x
        odom.pose.pose.position.y = self._pose.y
        qx, qy, qz, qw = yaw_to_quaternion(self._pose.yaw)
        odom.pose.pose.orientation.x = qx
        odom.pose.pose.orientation.y = qy
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.twist.twist.linear.x = self._last_linear
        odom.twist.twist.angular.z = self._last_angular
        odom.pose.covariance = self._diag_covariance(self.get_parameter('pose_covariance_diag').value)
        odom.twist.covariance = self._diag_covariance(self.get_parameter('twist_covariance_diag').value)
        self.odom_pub.publish(odom)
        if self.tf_broadcaster is not None and TransformStamped is not None:
            transform = TransformStamped()
            transform.header.stamp = odom.header.stamp
            transform.header.frame_id = odom.header.frame_id
            transform.child_frame_id = odom.child_frame_id
            transform.transform.translation.x = self._pose.x
            transform.transform.translation.y = self._pose.y
            transform.transform.translation.z = 0.0
            transform.transform.rotation.x = qx
            transform.transform.rotation.y = qy
            transform.transform.rotation.z = qz
            transform.transform.rotation.w = qw
            self.tf_broadcaster.sendTransform(transform)

    def publish_summary(self) -> None:
        """Publish JSON summary for monitor and API layers.

        Returns:
            None.

        Raises:
            None.
        """
        now = monotonic_time()
        stale = self._last_feedback_at == 0.0 or now - self._last_feedback_at > float(self.get_parameter('velocity_timeout_sec').value)
        payload = {
            'pose': {'x': self._pose.x, 'y': self._pose.y, 'yaw': self._pose.yaw},
            'linearVelocity': 0.0 if stale else self._last_linear,
            'angularVelocity': 0.0 if stale else self._last_angular,
            'stale': stale,
            'feedbackAvailable': self._last_feedback is not None,
            'descriptionLoaded': self._description_loaded,
            'robotName': self._description_robot_name,
        }
        msg = String()
        msg.data = safe_json_dumps(payload)
        self.summary_pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = RobotLocalizationNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
