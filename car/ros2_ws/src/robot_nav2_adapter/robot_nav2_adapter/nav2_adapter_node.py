from __future__ import annotations

from collections import deque
from typing import Any, Deque

import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from std_msgs.msg import Bool, String

from robot_localization.localization_math import Pose2D, quaternion_to_yaw
from robot_nav2_adapter.backend_claims import resolve_nav2_backend_runtime_claims
from robot_navigation.navigation_model import Goal2D, RoutePlan, build_path, compute_navigation_command, load_route_plan, validate_navigation_parameters
from robot_navigation.provider_contract import resolve_navigation_provider
from robot_utils.helpers import monotonic_time, safe_json_dumps
from robot_utils.qos_profiles import qos_for


class Nav2AdapterNode(Node):
    """Governed isolated navigation adapter lane.

    This lane keeps the provider-neutral ROS surface used by decision/control
    while reporting truthful backend claims. The in-repo implementation is the
    local adapter backend. An external Nav2 backend may only be selected when
    the environment advertises availability *and* this package explicitly marks
    the backend integration as implemented.
    """

    def __init__(self, node_name: str = 'robot_navigation') -> None:
        super().__init__(node_name)
        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('goal_pose_topic', '/robot/navigation/goal_pose')
        self.declare_parameter('goal_id_topic', '/robot/navigation/goal_id')
        self.declare_parameter('route_name_topic', '/robot/navigation/route_name')
        self.declare_parameter('cancel_topic', '/robot/navigation/cancel')
        self.declare_parameter('output_cmd_topic', '/robot/navigation/cmd_vel')
        self.declare_parameter('path_topic', '/robot/navigation/path')
        self.declare_parameter('status_topic', '/robot/navigation/status')
        self.declare_parameter('route_plan_path', '')
        self.declare_parameter('provider_name', 'nav2_provider')
        self.declare_parameter('backend_mode', 'auto')
        self.declare_parameter('external_nav2_stack_available', False)
        self.declare_parameter('external_nav2_backend_integrated', False)
        self.declare_parameter('map_id', 'default_map')
        self.declare_parameter('localization_source', 'odom_pose_fusion')
        self.declare_parameter('planner_id', 'isolated_lane_planner')
        self.declare_parameter('controller_id', 'isolated_lane_controller')
        self.declare_parameter('recovery_enabled', True)
        self.declare_parameter('pose_timeout_sec', 1.0)
        self.declare_parameter('goal_tolerance_m', 0.18)
        self.declare_parameter('goal_pose_terminal_yaw_enabled', False)
        self.declare_parameter('heading_slowdown_angle_rad', 0.0)
        self.declare_parameter('heading_slowdown_radius_m', 1.2)
        self.declare_parameter('final_yaw_tolerance_rad', 0.12)
        self.declare_parameter('rotate_in_place_threshold_rad', 0.7)
        self.declare_parameter('max_linear_m_s', 0.26)
        self.declare_parameter('max_angular_rad_s', 1.1)
        self.declare_parameter('angular_gain', 1.6)
        self.declare_parameter('linear_gain', 0.8)
        self.declare_parameter('control_rate_hz', 10.0)

        validate_navigation_parameters(
            goal_tolerance_m=float(self.get_parameter('goal_tolerance_m').value),
            heading_slowdown_angle_rad=float(self.get_parameter('heading_slowdown_angle_rad').value),
            heading_slowdown_radius_m=float(self.get_parameter('heading_slowdown_radius_m').value),
            final_yaw_tolerance_rad=float(self.get_parameter('final_yaw_tolerance_rad').value),
            rotate_in_place_threshold_rad=float(self.get_parameter('rotate_in_place_threshold_rad').value),
            max_linear_m_s=float(self.get_parameter('max_linear_m_s').value),
            max_angular_rad_s=float(self.get_parameter('max_angular_rad_s').value),
            angular_gain=float(self.get_parameter('angular_gain').value),
            linear_gain=float(self.get_parameter('linear_gain').value),
            control_rate_hz=float(self.get_parameter('control_rate_hz').value),
            goal_pose_terminal_yaw_enabled=bool(self.get_parameter('goal_pose_terminal_yaw_enabled').value),
        )
        self._provider = resolve_navigation_provider(str(self.get_parameter('provider_name').value))
        requested_backend_mode = str(self.get_parameter('backend_mode').value or 'auto').strip() or 'auto'
        self._backend_notes = self._resolve_backend_notes(requested_backend_mode)

        self._pose: Pose2D | None = None
        self._last_pose_at: float | None = None
        self._goal_queue: Deque[Goal2D] = deque()
        self._goal_ids: Deque[str] = deque()
        self._active_goal: Goal2D | None = None
        self._active_goal_id: str = ''
        self._route_plan = self._load_route_plan()
        self._active_route_name: str = ''
        self._total_goals: int = 0
        self._completed_goals: int = 0
        self._last_state: str = 'idle'
        self._last_reason: str = 'startup'
        self._heading_slowdown_deprecation_warned = False
        self._recovery_attempts: int = 0
        self._last_recovery_reason: str = ''

        self.cmd_pub = self.create_publisher(Twist, str(self.get_parameter('output_cmd_topic').value), qos_for('control_cmd'))
        self.path_pub = self.create_publisher(Path, str(self.get_parameter('path_topic').value), qos_for('telemetry'))
        self.status_pub = self.create_publisher(String, str(self.get_parameter('status_topic').value), qos_for('status_summary'))

        self.create_subscription(Odometry, str(self.get_parameter('odom_topic').value), self.on_odometry, qos_for('telemetry'))
        self.create_subscription(PoseStamped, str(self.get_parameter('goal_pose_topic').value), self.on_goal_pose, qos_for('control_cmd'))
        self.create_subscription(String, str(self.get_parameter('goal_id_topic').value), self.on_goal_id, qos_for('control_cmd'))
        self.create_subscription(String, str(self.get_parameter('route_name_topic').value), self.on_route_name, qos_for('control_cmd'))
        self.create_subscription(Bool, str(self.get_parameter('cancel_topic').value), self.on_cancel, qos_for('control_cmd'))
        self.control_timer = self.create_timer(1.0 / float(self.get_parameter('control_rate_hz').value), self.control_step)

    def _heading_slowdown_angle_rad(self) -> float:
        configured = float(self.get_parameter('heading_slowdown_angle_rad').value)
        if configured > 0.0:
            return configured
        legacy = float(self.get_parameter('heading_slowdown_radius_m').value)
        if not self._heading_slowdown_deprecation_warned:
            self.get_logger().warning('heading_slowdown_radius_m is deprecated; configure heading_slowdown_angle_rad instead')
            self._heading_slowdown_deprecation_warned = True
        return legacy

    def _resolve_backend_notes(self, backend_mode: str) -> dict[str, Any]:
        """Resolve the selected adapter backend and its runtime claims.

        Args:
            backend_mode: Requested backend selector.

        Returns:
            Serializable runtime description used in status payloads.

        Raises:
            None. Unsupported values fall back to the governed local adapter.
        """
        return resolve_nav2_backend_runtime_claims(
            requested_backend_mode=backend_mode,
            external_nav2_stack_available=bool(self.get_parameter('external_nav2_stack_available').value),
            external_nav2_backend_integrated=bool(self.get_parameter('external_nav2_backend_integrated').value),
            recovery_enabled=bool(self.get_parameter('recovery_enabled').value),
        )

    def _load_route_plan(self) -> RoutePlan | None:
        route_plan_path = str(self.get_parameter('route_plan_path').value or '').strip()
        if not route_plan_path:
            return None
        return load_route_plan(route_plan_path)

    def _publish_status_payload(self, payload: dict[str, object]) -> None:
        msg = String()
        msg.data = safe_json_dumps(payload)
        self.status_pub.publish(msg)

    def _pose_age_sec(self) -> float | None:
        if self._last_pose_at is None:
            return None
        return max(0.0, monotonic_time() - self._last_pose_at)

    def _pose_is_stale(self) -> bool:
        pose_age = self._pose_age_sec()
        if pose_age is None:
            return True
        return pose_age > float(self.get_parameter('pose_timeout_sec').value)

    def _payload(self, state: str, *, extra: dict[str, object] | None = None) -> dict[str, object]:
        active_goal = self._active_goal
        total_goals = max(int(self._total_goals), int(self._completed_goals) + (1 if active_goal is not None else 0) + len(self._goal_queue))
        progress = 1.0 if total_goals <= 0 else min(1.0, float(self._completed_goals) / float(total_goals))
        pose_age = self._pose_age_sec()
        payload: dict[str, object] = {
            'state': state,
            'routeName': self._active_route_name or None,
            'goalId': self._active_goal_id or None,
            'goalLabel': active_goal.label if active_goal is not None else None,
            'queuedGoals': len(self._goal_queue),
            'completedGoals': int(self._completed_goals),
            'totalGoals': int(total_goals),
            'progress': progress,
            'cmdSource': 'navigation',
            'reason': self._last_reason or None,
            'provider': self._provider.to_dict(),
            'providerLaneRuntime': dict(self._backend_notes),
            'health': {
                'healthy': not self._pose_is_stale(),
                'poseAgeSec': round(pose_age, 3) if pose_age is not None else None,
                'recoveryEnabled': bool(self.get_parameter('recovery_enabled').value),
                'recoveryAttempts': self._recovery_attempts,
                'lastRecoveryReason': self._last_recovery_reason or None,
                'localizationSource': str(self.get_parameter('localization_source').value),
                'mapId': str(self.get_parameter('map_id').value),
                'plannerId': str(self.get_parameter('planner_id').value),
                'controllerId': str(self.get_parameter('controller_id').value),
            },
        }
        if extra:
            payload.update(extra)
        return payload

    def on_odometry(self, msg: Odometry) -> None:
        """Update the current planar pose estimate from odometry.

        Args:
            msg: Odometry update used as the adapter's localization feed.

        Returns:
            None.

        Raises:
            None.
        """
        q = msg.pose.pose.orientation
        yaw = quaternion_to_yaw(float(q.x), float(q.y), float(q.z), float(q.w))
        self._pose = Pose2D(x=msg.pose.pose.position.x, y=msg.pose.pose.position.y, yaw=yaw)
        self._last_pose_at = monotonic_time()

    def _load_single_goal(self, goal: Goal2D, *, goal_id: str, reason: str) -> None:
        self._goal_queue.clear()
        self._goal_ids.clear()
        self._completed_goals = 0
        self._total_goals = 1
        self._active_route_name = ''
        self._active_goal = goal
        self._active_goal_id = goal_id
        self._last_state = 'goal_loaded'
        self._last_reason = reason
        self.publish_path_preview()
        self._publish_status_payload(self._payload('goal_loaded'))

    def on_goal_pose(self, msg: PoseStamped) -> None:
        yaw = None
        if bool(self.get_parameter('goal_pose_terminal_yaw_enabled').value):
            yaw = quaternion_to_yaw(
                float(msg.pose.orientation.x),
                float(msg.pose.orientation.y),
                float(msg.pose.orientation.z),
                float(msg.pose.orientation.w),
            )
        self._load_single_goal(
            Goal2D(x=float(msg.pose.position.x), y=float(msg.pose.position.y), yaw=yaw, label='pose_goal'),
            goal_id='pose_goal',
            reason='pose_goal_loaded',
        )

    def on_goal_id(self, msg: String) -> None:
        route_plan = self._route_plan
        goal_id = str(msg.data).strip()
        if route_plan is None:
            self._last_reason = 'route_plan_unavailable'
            self.publish_zero(reason='route_plan_unavailable', state='failed')
            return
        waypoint = route_plan.waypoints.get(goal_id)
        if waypoint is None:
            self._last_reason = f'unknown_goal_id:{goal_id}'
            self.publish_zero(reason=f'unknown_goal_id:{goal_id}', state='failed')
            return
        self._load_single_goal(
            Goal2D(x=waypoint.x, y=waypoint.y, yaw=waypoint.yaw, label=waypoint.label),
            goal_id=goal_id,
            reason='named_goal_loaded',
        )

    def on_route_name(self, msg: String) -> None:
        route_plan = self._route_plan
        route_name = str(msg.data).strip()
        if route_plan is None:
            self._last_reason = 'route_plan_unavailable'
            self.publish_zero(reason='route_plan_unavailable', state='failed')
            return
        route = route_plan.routes.get(route_name)
        if route is None:
            self._last_reason = f'unknown_route_name:{route_name}'
            self.publish_zero(reason=f'unknown_route_name:{route_name}', state='failed')
            return
        self._goal_queue.clear()
        self._goal_ids.clear()
        self._active_route_name = route_name
        self._completed_goals = 0
        self._total_goals = len(route)
        for waypoint_id in route:
            waypoint = route_plan.waypoints[waypoint_id]
            self._goal_queue.append(Goal2D(x=waypoint.x, y=waypoint.y, yaw=waypoint.yaw, label=waypoint.label))
            self._goal_ids.append(waypoint_id)
        self._active_goal = self._goal_queue.popleft() if self._goal_queue else None
        self._active_goal_id = self._goal_ids.popleft() if self._goal_ids else ''
        self._last_state = 'route_loaded'
        self._last_reason = 'route_loaded'
        self.publish_path_preview()
        self._publish_status_payload(self._payload('route_loaded'))

    def on_cancel(self, msg: Bool) -> None:
        if not bool(msg.data):
            return
        self._goal_queue.clear()
        self._goal_ids.clear()
        self._active_goal = None
        self._active_goal_id = ''
        self._last_state = 'cancelled'
        self._last_reason = 'cancelled'
        self.publish_zero(reason='cancelled', state='cancelled')

    def publish_zero(self, *, reason: str, state: str = 'idle') -> None:
        twist = Twist()
        self.cmd_pub.publish(twist)
        self._publish_status_payload(self._payload(state, extra={'reason': reason}))

    def publish_path_preview(self) -> None:
        if self._pose is None or self._active_goal is None:
            return
        path_points = build_path(start=self._pose, goal=self._active_goal)
        path = Path()
        path.header.stamp = self.get_clock().now().to_msg()
        path.header.frame_id = 'odom'
        for x, y in path_points:
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = x
            pose.pose.position.y = y
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)
        self.path_pub.publish(path)

    def _publish_recovery_status(self, *, reason: str) -> None:
        self._recovery_attempts += 1
        self._last_recovery_reason = reason
        self._last_state = 'recovering'
        self._last_reason = reason
        self.publish_zero(reason=reason, state='recovering')

    def control_step(self) -> None:
        """Run one adapter-lane control step with health and recovery guards.

        Returns:
            None.

        Raises:
            None. Invalid state collapses to a safe zero command and status.
        """
        if self._pose is None:
            self._last_reason = 'waiting_for_pose'
            self.publish_zero(reason='waiting_for_pose', state='waiting')
            return
        pose_is_stale = getattr(self, '_pose_is_stale', lambda: False)
        if pose_is_stale():
            if bool(self.get_parameter('recovery_enabled').value):
                self._publish_recovery_status(reason='pose_stale_wait_for_localization')
            else:
                self._last_reason = 'pose_stale'
                self.publish_zero(reason='pose_stale', state='degraded')
            return
        if self._active_goal is None:
            self._last_reason = 'waiting_for_goal'
            self.publish_zero(reason='waiting_for_goal', state='idle')
            return
        command = compute_navigation_command(
            pose=self._pose,
            goal=self._active_goal,
            max_linear_m_s=float(self.get_parameter('max_linear_m_s').value),
            max_angular_rad_s=float(self.get_parameter('max_angular_rad_s').value),
            goal_tolerance_m=float(self.get_parameter('goal_tolerance_m').value),
            angular_gain=float(self.get_parameter('angular_gain').value),
            linear_gain=float(self.get_parameter('linear_gain').value),
            heading_slowdown_angle_rad=self._heading_slowdown_angle_rad(),
            heading_slowdown_radius_m=float(self.get_parameter('heading_slowdown_radius_m').value),
            final_yaw_tolerance_rad=float(self.get_parameter('final_yaw_tolerance_rad').value),
            rotate_in_place_threshold_rad=float(self.get_parameter('rotate_in_place_threshold_rad').value),
        )
        if command.goal_reached:
            reached_goal_id = self._active_goal_id or self._active_goal.label
            reached_goal_label = self._active_goal.label
            self._completed_goals += 1
            if self._goal_queue:
                self._active_goal = self._goal_queue.popleft()
                self._active_goal_id = self._goal_ids.popleft() if self._goal_ids else ''
                self.publish_path_preview()
                self._last_state = 'goal_reached'
                self._last_reason = f'goal_reached:{reached_goal_id}'
                self._publish_status_payload(self._payload('goal_reached', extra={
                    'reachedGoalId': reached_goal_id,
                    'reachedGoalLabel': reached_goal_label,
                    'nextGoalId': self._active_goal_id or None,
                    'nextGoalLabel': self._active_goal.label if self._active_goal is not None else None,
                }))
                handoff = Twist()
                self.cmd_pub.publish(handoff)
                return
            self._active_goal = None
            self._active_goal_id = ''
            self._last_state = 'route_completed'
            self._last_reason = 'route_completed'
            self.publish_zero(reason='route_completed', state='route_completed')
            return
        twist = Twist()
        twist.linear.x = command.linear_x
        twist.angular.z = command.angular_z
        self.cmd_pub.publish(twist)
        state = 'aligning' if command.phase == 'align_yaw' else 'tracking'
        self._last_state = state
        self._last_reason = state
        self._publish_status_payload(self._payload(state, extra={
            'distanceM': command.distance_m,
            'headingErrorRad': command.heading_error_rad,
            'positionReached': command.position_reached,
            'yawErrorRad': command.yaw_error_rad,
            'phase': command.phase,
        }))


def main() -> None:
    rclpy.init()
    node = Nav2AdapterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
