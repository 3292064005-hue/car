from __future__ import annotations

from collections import deque
from typing import Deque

import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from std_msgs.msg import Bool, String

from robot_localization.localization_math import Pose2D
from robot_utils.helpers import safe_json_dumps
from robot_utils.qos_profiles import qos_for
from .navigation_model import Goal2D, RoutePlan, build_path, compute_navigation_command, load_route_plan
from .provider_contract import NavigationProviderContract, ensure_provider_runtime_supported, resolve_navigation_provider


class RobotNavigationNode(Node):
    """Simple waypoint navigator with explicit route-level lifecycle reporting.

    The node now acts as the authoritative patrol motion generator. Decision
    publishes route or goal intents, navigation computes velocity commands on a
    dedicated topic, and control arbitrates that source explicitly.
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
        self.declare_parameter('provider_name', 'simple_nav_provider')
        self.declare_parameter('goal_tolerance_m', 0.18)
        self.declare_parameter('heading_slowdown_radius_m', 1.2)
        self.declare_parameter('max_linear_m_s', 0.26)
        self.declare_parameter('max_angular_rad_s', 1.1)
        self.declare_parameter('angular_gain', 1.6)
        self.declare_parameter('linear_gain', 0.8)
        self.declare_parameter('control_rate_hz', 10.0)

        self._provider: NavigationProviderContract = ensure_provider_runtime_supported(
            resolve_navigation_provider(str(self.get_parameter('provider_name').value))
        )
        self._pose: Pose2D | None = None
        self._goal_queue: Deque[Goal2D] = deque()
        self._goal_ids: Deque[str] = deque()
        self._active_goal: Goal2D | None = None
        self._active_goal_id: str = ''
        self._route_plan = self._load_route_plan()
        self._active_route_name: str = ''
        self._route_goal_ids: list[str] = []
        self._total_goals: int = 0
        self._completed_goals: int = 0
        self._last_state: str = 'idle'
        self._last_reason: str = 'startup'

        self.cmd_pub = self.create_publisher(Twist, str(self.get_parameter('output_cmd_topic').value), qos_for('control_cmd'))
        self.path_pub = self.create_publisher(Path, str(self.get_parameter('path_topic').value), qos_for('telemetry'))
        self.status_pub = self.create_publisher(String, str(self.get_parameter('status_topic').value), qos_for('status_summary'))

        self.create_subscription(Odometry, str(self.get_parameter('odom_topic').value), self.on_odometry, qos_for('telemetry'))
        self.create_subscription(PoseStamped, str(self.get_parameter('goal_pose_topic').value), self.on_goal_pose, qos_for('control_cmd'))
        self.create_subscription(String, str(self.get_parameter('goal_id_topic').value), self.on_goal_id, qos_for('control_cmd'))
        self.create_subscription(String, str(self.get_parameter('route_name_topic').value), self.on_route_name, qos_for('control_cmd'))
        self.create_subscription(Bool, str(self.get_parameter('cancel_topic').value), self.on_cancel, qos_for('control_cmd'))
        self.control_timer = self.create_timer(1.0 / float(self.get_parameter('control_rate_hz').value), self.control_step)

    def _load_route_plan(self) -> RoutePlan | None:
        route_plan_path = str(self.get_parameter('route_plan_path').value or '').strip()
        if not route_plan_path:
            return None
        return load_route_plan(route_plan_path)

    def _set_idle(self, *, reason: str, state: str = 'idle') -> None:
        self._goal_queue.clear()
        self._goal_ids.clear()
        self._active_goal = None
        self._active_goal_id = ''
        self._active_route_name = '' if state != 'route_completed' else self._active_route_name
        self._last_state = state
        self._last_reason = reason
        self.publish_zero(reason=reason, state=state)

    def _append_goal(self, goal: Goal2D, *, goal_id: str = '') -> None:
        self._goal_queue.append(goal)
        self._goal_ids.append(str(goal_id or goal.label or ''))
        if self._active_goal is None:
            self._active_goal = self._goal_queue.popleft()
            self._active_goal_id = self._goal_ids.popleft() if self._goal_ids else ''
        self.publish_path_preview()

    def _goal_progress_payload(self, state: str, *, extra: dict[str, object] | None = None) -> dict[str, object]:
        active_goal = self._active_goal
        total_goals = max(int(self._total_goals), int(self._completed_goals) + (1 if active_goal is not None else 0) + len(self._goal_queue))
        progress = 1.0 if total_goals <= 0 else min(1.0, float(self._completed_goals) / float(total_goals))
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
        }
        if extra:
            payload.update(extra)
        return payload

    def on_odometry(self, msg: Odometry) -> None:
        """Update the current planar pose estimate from odometry."""
        q = msg.pose.pose.orientation
        yaw = 2.0 * __import__('math').atan2(q.z, q.w)
        self._pose = Pose2D(x=msg.pose.pose.position.x, y=msg.pose.pose.position.y, yaw=yaw)

    def on_goal_pose(self, msg: PoseStamped) -> None:
        """Replace the active mission with one pose goal."""
        self._goal_queue.clear()
        self._goal_ids.clear()
        self._completed_goals = 0
        self._total_goals = 1
        self._active_route_name = ''
        self._active_goal = None
        self._active_goal_id = 'pose_goal'
        self._append_goal(Goal2D(x=float(msg.pose.position.x), y=float(msg.pose.position.y), label='pose_goal'), goal_id='pose_goal')
        self._last_state = 'goal_loaded'
        self._last_reason = 'pose_goal_loaded'
        self._publish_status_payload(self._goal_progress_payload('goal_loaded'))

    def _publish_status_payload(self, payload: dict[str, object]) -> None:
        status = String()
        status.data = safe_json_dumps(payload)
        self.status_pub.publish(status)

    def on_goal_id(self, msg: String) -> None:
        """Load one named waypoint goal from the route plan."""
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
        self._goal_queue.clear()
        self._goal_ids.clear()
        self._completed_goals = 0
        self._total_goals = 1
        self._active_route_name = ''
        self._active_goal = None
        self._active_goal_id = goal_id
        self._append_goal(Goal2D(x=waypoint.x, y=waypoint.y, yaw=waypoint.yaw, label=waypoint.label), goal_id=goal_id)
        self._last_state = 'goal_loaded'
        self._last_reason = 'named_goal_loaded'
        self._publish_status_payload(self._goal_progress_payload('goal_loaded'))

    def on_route_name(self, msg: String) -> None:
        """Load one named route and publish mission metadata for decision/control."""
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
        self._active_goal = None
        self._active_goal_id = ''
        self._active_route_name = route_name
        self._route_goal_ids = list(route)
        self._total_goals = len(self._route_goal_ids)
        self._completed_goals = 0
        for waypoint_id in route:
            waypoint = route_plan.waypoints[waypoint_id]
            self._goal_queue.append(Goal2D(x=waypoint.x, y=waypoint.y, yaw=waypoint.yaw, label=waypoint.label))
            self._goal_ids.append(waypoint_id)
        self._active_goal = self._goal_queue.popleft() if self._goal_queue else None
        self._active_goal_id = self._goal_ids.popleft() if self._goal_ids else ''
        self.publish_path_preview()
        self._last_state = 'route_loaded'
        self._last_reason = 'route_loaded'
        self._publish_status_payload(self._goal_progress_payload('route_loaded'))

    def on_cancel(self, msg: Bool) -> None:
        """Cancel the active route or goal safely."""
        if bool(msg.data):
            self._last_reason = 'cancelled'
            self._set_idle(reason='cancelled', state='cancelled')

    def publish_zero(self, *, reason: str, state: str = 'idle') -> None:
        """Publish one zero command and the corresponding navigation state."""
        twist = Twist()
        self.cmd_pub.publish(twist)
        self._publish_status_payload(self._goal_progress_payload(state, extra={'reason': reason}))

    def publish_path_preview(self) -> None:
        """Publish the currently planned straight-line preview path."""
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

    def control_step(self) -> None:
        """Run one control step toward the active goal, if available.

        Returns:
            None.

        Raises:
            None. Invalid state is converted into a safe zero command and status output.
        """
        if self._pose is None:
            self._last_reason = 'waiting_for_pose'
            self.publish_zero(reason='waiting_for_pose', state='waiting')
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
            heading_slowdown_radius_m=float(self.get_parameter('heading_slowdown_radius_m').value),
            angular_gain=float(self.get_parameter('angular_gain').value),
            linear_gain=float(self.get_parameter('linear_gain').value),
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
                self._publish_status_payload(self._goal_progress_payload('goal_reached', extra={
                    'reachedGoalId': reached_goal_id,
                    'reachedGoalLabel': reached_goal_label,
                    'nextGoalId': self._active_goal_id or None,
                    'nextGoalLabel': self._active_goal.label if self._active_goal is not None else None,
                }))
            else:
                route_name = self._active_route_name
                self._active_goal = None
                self._active_goal_id = ''
                self._last_state = 'route_completed'
                self._last_reason = 'route_completed'
                self.publish_zero(reason='route_completed', state='route_completed')
                self._active_route_name = route_name
                return
        twist = Twist()
        twist.linear.x = command.linear_x
        twist.angular.z = command.angular_z
        self.cmd_pub.publish(twist)
        self._last_state = 'tracking'
        self._last_reason = 'tracking'
        self._publish_status_payload(
            self._goal_progress_payload(
                'tracking',
                extra={
                    'distanceM': command.distance_m,
                    'headingErrorRad': command.heading_error_rad,
                },
            )
        )


def main() -> None:
    rclpy.init()
    node = RobotNavigationNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
