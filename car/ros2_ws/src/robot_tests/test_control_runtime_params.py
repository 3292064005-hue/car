from __future__ import annotations

import sys
from types import ModuleType


def _install_ros_stubs() -> None:
    if 'rclpy' not in sys.modules:
        rclpy = ModuleType('rclpy')
        sys.modules['rclpy'] = rclpy
    if 'rclpy.node' not in sys.modules:
        node_mod = ModuleType('rclpy.node')

        class Node:
            pass

        node_mod.Node = Node
        sys.modules['rclpy.node'] = node_mod


_install_ros_stubs()

import robot_control.control_node as control_node_module
from robot_control.control_node import ControlNode
from std_msgs.msg import String


class _FakeNode:
    def __init__(self) -> None:
        self.runtime_param_overrides = {}
        self.event_pub = object()

    def get_logger(self):
        class _Logger:
            def warning(self, msg):
                pass

            def error(self, msg):
                pass
        return _Logger()


def test_control_runtime_params_invalid_payload_emits_policy_outcome(monkeypatch) -> None:
    node = _FakeNode()
    msg = String()
    msg.data = '{bad json'
    calls = []
    monkeypatch.setattr(control_node_module, 'publish_policy_outcome', lambda _node, *, outcome, event_pub: calls.append(event_pub))

    ControlNode.on_runtime_params(node, msg)

    assert calls == [node.event_pub]
