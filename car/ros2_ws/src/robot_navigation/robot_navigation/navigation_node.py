from __future__ import annotations

from collections import deque
from typing import Any, Deque

import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from std_msgs.msg import Bool, String

from robot_localization.localization_math import Pose2D, quaternion_to_yaw
from robot_utils.helpers import safe_json_dumps
from robot_utils.qos_profiles import qos_for
from .navigation_model import Goal2D, RoutePlan, Waypoint, build_path, compute_navigation_command, load_route_plan, validate_navigation_parameters
from .provider_contract import NavigationProviderContract, NavigationProviderRuntime, ensure_provider_runtime_supported, resolve_navigation_provider


class SimpleNavigationProviderRuntime:
    """Runtime adapter for the built-in simple navigation provider.

    Args:
        node: Owning ``RobotNavigationNode``. The adapter mutates only the
            provider-owned route/goal state on the node and returns normalized
            status payloads; ROS publication remains in the node boundary.

    Returns:
        Concrete implementation of ``NavigationProviderRuntime``.

    Raises:
        None directly. Missing route plans and unknown routes are converted into
        ``failed`` status payloads.

    Boundary behavior:
        The adapter intentionally does not import Nav2 action classes. A future
        Nav2 runtime can implement the same methods and map action feedback into
        the same normalized status vocabulary without changing decision/control
        callers.
    """

    def __init__(self, node: Any) -> None:
        self._node = node

    def readiness(self) -> dict[str, Any]:
        if getattr(self._node, '_pose', None) is None:
            return {'ready': False, 'state': 'blocked', 'reason': 'waiting_for_pose'}
        if getattr(self._node, '_active_goal', None) is None:
            return {'ready': False, 'state': 'idle', 'reason': 'waiting_for_goal'}
        return {'ready': True, 'state': 'ready', 'reason': 'ready'}

    def load_route(self, route_name: str) -> dict[str, Any]:
        route_plan = getattr(self._node, '_route_plan', None)
        normalized_route = str(route_name or '').strip()
        if route_plan is None:
            self._node._last_state = 'failed'
            self._node._last_reason = 'route_plan_unavailable'
            return self._node._goal_progress_payload('failed', extra={'reason': 'route_plan_unavailable'})
        route = route_plan.routes.get(normalized_route)
        if route is None:
            self._node._last_state = 'failed'
            self._node._last_reason = f'unknown_route_name:{normalized_route}'
            return self._node._goal_progress_payload('failed', extra={'reason': f'unknown_route_name:{normalized_route}'})
        self._node._goal_queue.clear()
        self._node._goal_ids.clear()
        self._node._active_goal = None
        self._node._active_goal_id = ''
        self._node._active_route_name = normalized_route
        self._node._route_goal_ids = list(route)
        self._node._total_goals = len(self._node._route_goal_ids)
        self._node._completed_goals = 0
        for waypoint_id in route:
            waypoint: Waypoint = route_plan.waypoints[waypoint_id]
            self._node._goal_queue.append(Goal2D(x=waypoint.x, y=waypoint.y, yaw=waypoint.yaw, label=waypoint.label))
            self._node._goal_ids.append(waypoint_id)
        self._node._active_goal = _pop_goal_queue(self._node._goal_queue) if self._node._goal_queue else None
        self._node._active_goal_id = _pop_goal_queue(self._node._goal_ids) if self._node._goal_ids else ''
        self._node._last_state = 'route_loaded'
        self._node._last_reason = 'route_loaded'
        self._node.publish_path_preview()
        return self._node._goal_progress_payload('route_loaded')

    def start_route(self, route_name: str) -> dict[str, Any]:
        status = self.load_route(route_name)
        if status.get('state') == 'failed':
            return status
        readiness = self.readiness()
        if not readiness.get('ready') and readiness.get('state') == 'blocked':
            self._node._last_state = 'blocked'
            self._node._last_reason = str(readiness.get('reason') or 'blocked')
            return self._node._goal_progress_payload('blocked', extra={'reason': self._node._last_reason})
        return status

    def pause(self) -> dict[str, Any]:
        self._node._last_state = 'paused'
        self._node._last_reason = 'paused'
        return self._node._goal_progress_payload('paused')

    def resume(self) -> dict[str, Any]:
        readiness = self.readiness()
        if not readiness.get('ready'):
            self._node._last_state = str(readiness.get('state') or 'blocked')
            self._node._last_reason = str(readiness.get('reason') or 'not_ready')
            return self._node._goal_progress_payload(self._node._last_state, extra={'reason': self._node._last_reason})
        self._node._last_state = 'tracking'
        self._node._last_reason = 'resume'
        return self._node._goal_progress_payload('tracking')

    def cancel(self) -> dict[str, Any]:
        self._node._goal_queue.clear()
        self._node._goal_ids.clear()
        self._node._active_goal = None
        self._node._active_goal_id = ''
        self._node._active_route_name = ''
        self._node._last_state = 'cancelled'
        self._node._last_reason = 'cancelled'
        return self._node._goal_progress_payload('cancelled', extra={'reason': 'cancelled'})

    def get_status(self) -> dict[str, Any]:
        state = str(getattr(self._node, '_last_state', 'idle') or 'idle')
        return self._node._goal_progress_payload(state, extra={'reason': getattr(self._node, '_last_reason', '') or None})


def _pop_goal_queue(queue: Any) -> Any:
    """Pop one queued navigation item from either deque or list test doubles."""
    if hasattr(queue, 'popleft'):
        return queue.popleft()
    return queue.pop(0)


def _provider_runtime_for(node: Any) -> NavigationProviderRuntime:
    runtime = getattr(node, '_provider_runtime', None)
    if runtime is None:
        runtime = SimpleNavigationProviderRuntime(node)
        setattr(node, '_provider_runtime', runtime)
    return runtime


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
        self._provider_runtime: NavigationProviderRuntime = SimpleNavigationProviderRuntime(self)
        self._heading_slowdown_deprecation_warned = False

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


    def _heading_slowdown_angle_rad(self) -> float:
        configured = float(self.get_parameter('heading_slowdown_angle_rad').value)
        if configured > 0.0:
            return configured
        legacy = float(self.get_parameter('heading_slowdown_radius_m').value)
        if not self._heading_slowdown_deprecation_warned:
            self.get_logger().warning('heading_slowdown_radius_m is deprecated; configure heading_slowdown_angle_rad instead')
            self._heading_slowdown_deprecation_warned = True
        return legacy

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
        yaw = quaternion_to_yaw(float(q.x), float(q.y), float(q.z), float(q.w))
        self._pose = Pose2D(x=msg.pose.pose.position.x, y=msg.pose.pose.position.y, yaw=yaw)

    def on_goal_pose(self, msg: PoseStamped) -> None:
        """Replace the active mission with one pose goal."""
        yaw = None
        if bool(self.get_parameter('goal_pose_terminal_yaw_enabled').value):
            yaw = quaternion_to_yaw(
                float(msg.pose.orientation.x),
                float(msg.pose.orientation.y),
                float(msg.pose.orientation.z),
                float(msg.pose.orientation.w),
            )
        self._goal_queue.clear()
        self._goal_ids.clear()
        self._completed_goals = 0
        self._total_goals = 1
        self._active_route_name = ''
        self._active_goal = None
        self._active_goal_id = 'pose_goal'
        self._append_goal(
            Goal2D(
                x=float(msg.pose.position.x),
                y=float(msg.pose.position.y),
                yaw=yaw,
                label='pose_goal',
            ),
            goal_id='pose_goal',
        )
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
        """Load and start one named route through the active provider runtime.

        Args:
            msg: Route-name message. Empty or unknown names are converted into
                provider ``failed`` status payloads.

        Returns:
            None. The normalized provider status is published to the navigation
            status topic.

        Raises:
            None. Provider errors are caught and surfaced as failed status.

        Boundary behavior:
            The node no longer mutates route execution state directly on this
            path; it delegates to ``NavigationProviderRuntime.start_route`` so
            the simple and future Nav2 providers share one runtime call chain.
        """
        route_name = str(msg.data).strip()
        try:
            payload = _provider_runtime_for(self).start_route(route_name)
        except Exception as exc:
            self._last_state = 'failed'
            self._last_reason = f'provider_error:{exc}'
            payload = self._goal_progress_payload('failed', extra={'reason': self._last_reason})
        self._publish_status_payload(payload)

    def on_cancel(self, msg: Bool) -> None:
        """Cancel the active route or goal safely through the provider runtime."""
        if bool(msg.data):
            _provider_runtime_for(self).cancel()
            self.publish_zero(reason='cancelled', state='cancelled')

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
        readiness = _provider_runtime_for(self).readiness()
        if not bool(readiness.get('ready')):
            reason = str(readiness.get('reason') or 'not_ready')
            state = str(readiness.get('state') or 'blocked')
            self._last_reason = reason
            self._last_state = state
            self.publish_zero(reason=reason, state=state)
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
                self._publish_status_payload(self._goal_progress_payload('goal_reached', extra={
                    'reachedGoalId': reached_goal_id,
                    'reachedGoalLabel': reached_goal_label,
                    'nextGoalId': self._active_goal_id or None,
                    'nextGoalLabel': self._active_goal.label if self._active_goal is not None else None,
                }))
                handoff = Twist()
                self.cmd_pub.publish(handoff)
                return
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
        state = 'aligning' if command.phase == 'align_yaw' else 'tracking'
        self._last_state = state
        self._last_reason = state
        self._publish_status_payload(
            self._goal_progress_payload(
                state,
                extra={
                    'distanceM': command.distance_m,
                    'headingErrorRad': command.heading_error_rad,
                    'positionReached': command.position_reached,
                    'yawErrorRad': command.yaw_error_rad,
                    'phase': command.phase,
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
