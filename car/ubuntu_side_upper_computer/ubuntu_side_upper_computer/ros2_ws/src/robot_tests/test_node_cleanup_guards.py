from __future__ import annotations

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
        geom.Twist = type('Twist', (), {})
        sys.modules['geometry_msgs.msg'] = geom
    if 'std_msgs.msg' not in sys.modules:
        std = ModuleType('std_msgs.msg')
        std.String = type('String', (), {'__init__': lambda self, data='': setattr(self, 'data', data)})
        sys.modules['std_msgs.msg'] = std
    if 'robot_msgs.msg' not in sys.modules:
        robot_msg = ModuleType('robot_msgs.msg')
        for name in ['ChassisState', 'EventLog', 'Fault', 'ModeState', 'PowerState', 'SpeakRequest', 'SystemStatus', 'VisionTarget', 'VoiceCommand']:
            setattr(robot_msg, name, type(name, (), {}))
        sys.modules['robot_msgs.msg'] = robot_msg
    if 'robot_msgs.srv' not in sys.modules:
        robot_srv = ModuleType('robot_msgs.srv')
        for name in ['ResetFault', 'SaveSnapshot', 'SetMode']:
            setattr(robot_srv, name, type(name, (), {'Request': type('Request', (), {})}))
        sys.modules['robot_msgs.srv'] = robot_srv


_install_ros_stubs()

from robot_web_bridge.web_bridge_node import RobotWebBridgeNode
from robot_vision.vision_node import VisionNode


class _Boom:
    def __init__(self, calls: list[str], name: str) -> None:
        self.calls = calls
        self.name = name

    def stop(self) -> None:
        self.calls.append(self.name)
        raise RuntimeError('cleanup failed')

    def close(self) -> None:
        self.calls.append(self.name)
        raise RuntimeError('cleanup failed')

    def destroy(self) -> None:
        self.calls.append(self.name)
        raise RuntimeError('cleanup failed')


def test_web_bridge_destroy_node_swallows_gateway_cleanup_error() -> None:
    calls: list[str] = []
    node = type('Stub', (), {'gateway': _Boom(calls, 'gateway')})()
    assert RobotWebBridgeNode.destroy_node(node) is True
    assert calls == ['gateway']


def test_vision_destroy_node_swallows_cleanup_errors() -> None:
    calls: list[str] = []
    node = type('Stub', (), {'client': _Boom(calls, 'client'), 'snapshots': _Boom(calls, 'snapshots'), 'snapshot_action_server': _Boom(calls, 'action')})()
    assert VisionNode.destroy_node(node) is True
    assert calls == ['client', 'snapshots', 'action']
