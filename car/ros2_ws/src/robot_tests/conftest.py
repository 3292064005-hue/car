from __future__ import annotations
from types import ModuleType, SimpleNamespace
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ROS_SRC_ROOT = REPO_ROOT / 'ros2_ws' / 'src'
for pkg in sorted(ROS_SRC_ROOT.iterdir()):
    if pkg.is_dir():
        pkg_str = str(pkg)
        if pkg_str not in sys.path:
            sys.path.insert(0, pkg_str)


def _ensure_module(name: str) -> ModuleType:
    module = sys.modules.get(name)
    if isinstance(module, ModuleType):
        return module
    module = ModuleType(name)
    sys.modules[name] = module
    return module


def _simple_message_type(name: str):
    class _Message:
        def __init__(self, **kwargs):
            self.stamp = SimpleNamespace(sec=0, nanosec=0)
            self.header = SimpleNamespace(frame_id='', stamp=SimpleNamespace(sec=0, nanosec=0))
            self.data = ''
            for key, value in kwargs.items():
                setattr(self, key, value)
    _Message.__name__ = name
    return _Message


def _service_type(name: str):
    class Request:
        def __init__(self, **kwargs):
            self.trace_id = ''
            self.requested_by = ''
            self.reason = ''
            self.mode = ''
            self.filename = ''
            self.text = ''
            self.priority = 0
            for key, value in kwargs.items():
                setattr(self, key, value)

    class Response:
        def __init__(self, **kwargs):
            self.success = False
            self.message = ''
            self.filepath = ''
            for key, value in kwargs.items():
                setattr(self, key, value)

    return type(name, (), {'Request': Request, 'Response': Response})


def _action_type(name: str):
    goal = _simple_message_type('Goal')
    result = _simple_message_type('Result')
    feedback = _simple_message_type('Feedback')
    return type(name, (), {'Goal': goal, 'Result': result, 'Feedback': feedback})


def _install_ros_test_stubs() -> None:
    try:
        import geometry_msgs.msg  # type: ignore
        import std_msgs.msg  # type: ignore
        import robot_msgs.msg  # type: ignore
        return
    except Exception:
        pass

    geom_pkg = _ensure_module('geometry_msgs')
    geom_msg = _ensure_module('geometry_msgs.msg')
    class Twist:
        def __init__(self):
            self.linear = SimpleNamespace(x=0.0, y=0.0, z=0.0)
            self.angular = SimpleNamespace(x=0.0, y=0.0, z=0.0)
    class PoseStamped:
        def __init__(self):
            self.header = SimpleNamespace(frame_id='', stamp=SimpleNamespace(sec=0, nanosec=0))
            self.pose = SimpleNamespace(position=SimpleNamespace(x=0.0, y=0.0, z=0.0), orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0))
    class TransformStamped:
        def __init__(self):
            self.header = SimpleNamespace(frame_id='', stamp=SimpleNamespace(sec=0, nanosec=0))
            self.child_frame_id = ''
            self.transform = SimpleNamespace(translation=SimpleNamespace(x=0.0, y=0.0, z=0.0), rotation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0))
    geom_msg.Twist = Twist
    geom_msg.PoseStamped = PoseStamped
    geom_msg.TransformStamped = TransformStamped
    geom_pkg.msg = geom_msg

    std_pkg = _ensure_module('std_msgs')
    std_msg = _ensure_module('std_msgs.msg')
    class String:
        def __init__(self, data: str = ''):
            self.data = data
    class Bool:
        def __init__(self, data: bool = False):
            self.data = data
    std_msg.String = String
    std_msg.Bool = Bool
    std_pkg.msg = std_msg

    builtin_pkg = _ensure_module('builtin_interfaces')
    builtin_msg = _ensure_module('builtin_interfaces.msg')
    class Time:
        def __init__(self, sec: int = 0, nanosec: int = 0):
            self.sec = sec
            self.nanosec = nanosec
    builtin_msg.Time = Time
    builtin_pkg.msg = builtin_msg

    nav_pkg = _ensure_module('nav_msgs')
    nav_msg = _ensure_module('nav_msgs.msg')
    class Path:
        def __init__(self):
            self.header = SimpleNamespace(frame_id='')
            self.poses = []
    class Odometry:
        def __init__(self):
            self.header = SimpleNamespace(frame_id='')
            self.pose = SimpleNamespace(pose=SimpleNamespace(position=SimpleNamespace(x=0.0, y=0.0, z=0.0), orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)))
            self.twist = SimpleNamespace(twist=SimpleNamespace(linear=SimpleNamespace(x=0.0, y=0.0, z=0.0), angular=SimpleNamespace(x=0.0, y=0.0, z=0.0)))
    nav_msg.Path = Path
    nav_msg.Odometry = Odometry
    nav_pkg.msg = nav_msg

    sensor_pkg = _ensure_module('sensor_msgs')
    sensor_msg = _ensure_module('sensor_msgs.msg')
    sensor_msg.BatteryState = _simple_message_type('BatteryState')
    sensor_msg.JointState = _simple_message_type('JointState')
    sensor_pkg.msg = sensor_msg

    diagnostic_pkg = _ensure_module('diagnostic_msgs')
    diagnostic_msg = _ensure_module('diagnostic_msgs.msg')
    diagnostic_msg.DiagnosticArray = _simple_message_type('DiagnosticArray')
    diagnostic_msg.DiagnosticStatus = _simple_message_type('DiagnosticStatus')
    diagnostic_msg.KeyValue = _simple_message_type('KeyValue')
    diagnostic_pkg.msg = diagnostic_msg

    lifecycle_pkg = _ensure_module('lifecycle_msgs')
    lifecycle_msg = _ensure_module('lifecycle_msgs.msg')
    lifecycle_srv = _ensure_module('lifecycle_msgs.srv')
    lifecycle_msg.Transition = _simple_message_type('Transition')
    lifecycle_srv.ChangeState = _service_type('ChangeState')
    lifecycle_srv.GetState = _service_type('GetState')
    lifecycle_pkg.msg = lifecycle_msg
    lifecycle_pkg.srv = lifecycle_srv

    robot_pkg = _ensure_module('robot_msgs')
    robot_msg = _ensure_module('robot_msgs.msg')
    for name in ['ChassisState','EventLog','Fault','ModeState','PowerState','SpeakRequest','SystemStatus','VisionTarget','VoiceCommand']:
        setattr(robot_msg, name, _simple_message_type(name))
    robot_srv = _ensure_module('robot_msgs.srv')
    for name in ['ResetFault','SaveSnapshot','SetMode']:
        setattr(robot_srv, name, _service_type(name))
    robot_action = _ensure_module('robot_msgs.action')
    for name in ['StartPatrol','TrackTarget','SaveSnapshotTask']:
        setattr(robot_action, name, _action_type(name))
    robot_pkg.msg = robot_msg
    robot_pkg.srv = robot_srv
    robot_pkg.action = robot_action

    rclpy_pkg = _ensure_module('rclpy')
    rclpy_node = _ensure_module('rclpy.node')
    rclpy_exec = _ensure_module('rclpy.executors')
    rclpy_action = _ensure_module('rclpy.action')
    class Node:
        def __init__(self, *args, **kwargs):
            pass
    class MultiThreadedExecutor:
        def __init__(self, *args, **kwargs):
            pass
    class ActionClient:
        def __init__(self, *args, **kwargs):
            pass
        def wait_for_server(self, timeout_sec=0.0):
            return False
    rclpy_node.Node = Node
    rclpy_exec.MultiThreadedExecutor = MultiThreadedExecutor
    rclpy_action.ActionClient = ActionClient
    rclpy_action.ActionServer = _simple_message_type('ActionServer')
    rclpy_action.CancelResponse = type('CancelResponse', (), {'ACCEPT': True, 'REJECT': False})
    rclpy_action.GoalResponse = type('GoalResponse', (), {'ACCEPT': True, 'REJECT': False})
    rclpy_pkg.node = rclpy_node
    rclpy_pkg.executors = rclpy_exec
    rclpy_pkg.action = rclpy_action
    rclpy_pkg.init = lambda *args, **kwargs: None
    rclpy_pkg.shutdown = lambda *args, **kwargs: None
    rclpy_pkg.spin = lambda *args, **kwargs: None


_install_ros_test_stubs()



"""Test-suite hygiene fixtures for canonical-source verification.

These fixtures make sure repo-root regression tests do not leave build/install or
frontend dependency artifacts behind when they synthesize tool outputs under the
canonical source tree. Existing user worktrees are preserved: only paths created
by the current test are removed afterwards.
"""

import shutil
from pathlib import Path

import pytest

MUTABLE_ARTIFACT_PATHS = (
    REPO_ROOT / 'ros2_ws' / 'install',
    REPO_ROOT / 'robot_frontend' / 'node_modules',
    REPO_ROOT / 'robot_frontend' / 'dist',
    REPO_ROOT / 'log',
)


@pytest.fixture(autouse=True)
def restore_canonical_artifact_dirs() -> None:
    existed_before = {path: path.exists() for path in MUTABLE_ARTIFACT_PATHS}
    yield
    for path, already_existed in existed_before.items():
        if already_existed:
            continue
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
