from __future__ import annotations

from collections import deque
import sys
from types import ModuleType


def _install_ros_stubs() -> None:
    if 'rclpy' not in sys.modules:
        sys.modules['rclpy'] = ModuleType('rclpy')
    if 'rclpy.node' not in sys.modules:
        node_mod = ModuleType('rclpy.node')

        class Node:
            pass

        node_mod.Node = Node
        sys.modules['rclpy.node'] = node_mod
    if 'geometry_msgs.msg' not in sys.modules:
        geom = ModuleType('geometry_msgs.msg')
        geom.PoseStamped = type('PoseStamped', (), {})

        class Twist:
            def __init__(self) -> None:
                self.linear = type('Linear', (), {'x': 0.0})()
                self.angular = type('Angular', (), {'z': 0.0})()

        geom.Twist = Twist
        sys.modules['geometry_msgs.msg'] = geom
    if 'nav_msgs.msg' not in sys.modules:
        nav = ModuleType('nav_msgs.msg')
        nav.Odometry = type('Odometry', (), {})
        nav.Path = type('Path', (), {})
        sys.modules['nav_msgs.msg'] = nav
    if 'std_msgs.msg' not in sys.modules:
        std = ModuleType('std_msgs.msg')
        std.Bool = type('Bool', (), {})
        std.String = type('String', (), {'__init__': lambda self: setattr(self, 'data', '')})
        sys.modules['std_msgs.msg'] = std


_install_ros_stubs()

from robot_localization.localization_math import Pose2D, yaw_to_quaternion
from robot_navigation.navigation_model import Goal2D, RoutePlan, Waypoint
from robot_navigation.navigation_node import RobotNavigationNode, SimpleNavigationProviderRuntime


class _Publisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, msg) -> None:
        self.messages.append(msg)


class _Parameter:
    def __init__(self, value) -> None:
        self.value = value


class _NodeStub:
    def __init__(self) -> None:
        self._pose = Pose2D(x=0.05, y=0.0, yaw=0.0)
        self._active_goal = Goal2D(x=0.0, y=0.0, yaw=1.57, label='dock')
        self._active_goal_id = 'P1'
        self._goal_queue = []
        self._goal_ids = []
        self._completed_goals = 0
        self._active_route_name = ''
        self._last_state = 'goal_loaded'
        self._last_reason = 'goal_loaded'
        self._provider = type('Provider', (), {'to_dict': lambda self: {'name': 'stub'}})()
        self.cmd_pub = _Publisher()
        self.status_pub = _Publisher()
        self._heading_slowdown_deprecation_warned = False
        self.params = {
            'max_linear_m_s': 0.26,
            'max_angular_rad_s': 1.1,
            'goal_tolerance_m': 0.18,
            'goal_pose_terminal_yaw_enabled': False,
            'angular_gain': 1.6,
            'linear_gain': 0.8,
            'heading_slowdown_angle_rad': 1.2,
            'heading_slowdown_radius_m': 1.2,
            'final_yaw_tolerance_rad': 0.12,
            'rotate_in_place_threshold_rad': 0.7,
        }

    def get_parameter(self, name: str):
        return _Parameter(self.params[name])

    def get_logger(self):
        return type('Logger', (), {'warning': lambda self, msg: None})()

    def _heading_slowdown_angle_rad(self) -> float:
        return 1.2

    def _goal_progress_payload(self, state: str, *, extra=None):
        payload = {'state': state}
        if extra:
            payload.update(extra)
        return payload

    def _publish_status_payload(self, payload) -> None:
        self.status_pub.publish(payload)


    def _append_goal(self, goal, *, goal_id: str = '') -> None:
        self._active_goal = goal
        self._active_goal_id = goal_id

    def publish_zero(self, *, reason: str, state: str = 'idle') -> None:
        self._publish_status_payload({'state': state, 'reason': reason})

    def publish_path_preview(self) -> None:
        pass


def test_navigation_node_holds_active_goal_until_terminal_yaw_aligned() -> None:
    node = _NodeStub()

    RobotNavigationNode.control_step(node)

    assert node._active_goal is not None
    assert node._active_goal_id == 'P1'
    assert node._completed_goals == 0
    assert node._last_state == 'aligning'
    assert node.cmd_pub.messages[-1].linear.x == 0.0
    assert node.cmd_pub.messages[-1].angular.z > 0.0
    assert node.status_pub.messages[-1]['phase'] == 'align_yaw'


def test_navigation_node_goal_pose_keeps_legacy_position_only_semantics_by_default() -> None:
    node = _NodeStub()
    node._active_goal = None
    node._goal_queue = []
    node._goal_ids = []
    node._completed_goals = 0
    node._total_goals = 0

    qx, qy, qz, qw = yaw_to_quaternion(0.9)
    msg = type('PoseStamped', (), {
        'pose': type('Pose', (), {
            'position': type('Position', (), {'x': 1.2, 'y': -0.4})(),
            'orientation': type('Orientation', (), {'x': qx, 'y': qy, 'z': qz, 'w': qw})(),
        })(),
    })()

    RobotNavigationNode.on_goal_pose(node, msg)

    assert node._active_goal is not None
    assert node._active_goal.label == 'pose_goal'
    assert node._active_goal.yaw is None


def test_navigation_node_goal_pose_can_opt_into_terminal_yaw_alignment() -> None:
    node = _NodeStub()
    node.params['goal_pose_terminal_yaw_enabled'] = True
    node._active_goal = None
    node._goal_queue = []
    node._goal_ids = []
    node._completed_goals = 0
    node._total_goals = 0

    qx, qy, qz, qw = yaw_to_quaternion(0.9)
    msg = type('PoseStamped', (), {
        'pose': type('Pose', (), {
            'position': type('Position', (), {'x': 1.2, 'y': -0.4})(),
            'orientation': type('Orientation', (), {'x': qx, 'y': qy, 'z': qz, 'w': qw})(),
        })(),
    })()

    RobotNavigationNode.on_goal_pose(node, msg)

    assert node._active_goal is not None
    assert node._active_goal.yaw is not None
    assert abs(node._active_goal.yaw - 0.9) < 1e-6


def test_navigation_node_intermediate_goal_handoff_publishes_zero_and_returns_before_tracking_next_goal() -> None:
    node = _NodeStub()
    node._pose = Pose2D(x=0.0, y=0.0, yaw=0.0)
    node._active_goal = Goal2D(x=0.0, y=0.0, label='P1')
    node._active_goal_id = 'P1'
    node._goal_queue = deque([Goal2D(x=1.0, y=0.0, label='P2')])
    node._goal_ids = deque(['P2'])

    RobotNavigationNode.control_step(node)

    assert node._active_goal is not None
    assert node._active_goal.label == 'P2'
    assert node._active_goal_id == 'P2'
    assert node._last_state == 'goal_reached'
    assert node.status_pub.messages[-1]['state'] == 'goal_reached'
    assert node.status_pub.messages[-1]['nextGoalId'] == 'P2'
    assert node.cmd_pub.messages[-1].linear.x == 0.0
    assert node.cmd_pub.messages[-1].angular.z == 0.0


def test_navigation_route_name_uses_provider_runtime_call_chain() -> None:
    node = _NodeStub()
    node._pose = Pose2D(x=0.0, y=0.0, yaw=0.0)
    node._route_plan = RoutePlan(
        waypoints={
            'P1': Waypoint(id='P1', x=1.0, y=0.0, label='dock'),
            'P2': Waypoint(id='P2', x=2.0, y=0.0, label='exit'),
        },
        routes={'patrol': ('P1', 'P2')},
    )
    node._provider_runtime = SimpleNavigationProviderRuntime(node)
    msg = type('String', (), {'data': 'patrol'})()

    RobotNavigationNode.on_route_name(node, msg)

    assert node._active_route_name == 'patrol'
    assert node._active_goal_id == 'P1'
    assert node._goal_ids[0] == 'P2'
    assert node.status_pub.messages[-1]['state'] == 'route_loaded'


def test_navigation_cancel_uses_provider_runtime_call_chain() -> None:
    node = _NodeStub()
    node._provider_runtime = SimpleNavigationProviderRuntime(node)
    msg = type('Bool', (), {'data': True})()

    RobotNavigationNode.on_cancel(node, msg)

    assert node._active_goal is None
    assert node._active_goal_id == ''
    assert node._last_state == 'cancelled'
    assert node.status_pub.messages[-1]['state'] == 'cancelled'
