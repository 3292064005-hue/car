from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace


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

from std_msgs.msg import String
from robot_decision.decision_node import DecisionNode
from robot_contracts.runtime_param_transport import build_runtime_param_payload, dumps_runtime_param_payload


class _DecisionRuntimeStub:
    def __init__(self) -> None:
        self._runtime_param_overrides = {}
        self.track_manager = SimpleNamespace(max_linear=0.18, max_angular=0.9, offset_deadband=0.05)
        self.event_pub = None

    def _runtime_param_value(self, key: str, default: float) -> float:
        return DecisionNode._runtime_param_value(self, key, default)


def test_decision_node_updates_track_manager_from_runtime_params() -> None:
    node = _DecisionRuntimeStub()
    msg = String()
    msg.data = dumps_runtime_param_payload(
        build_runtime_param_payload(
            {'maxLinearSpeed': 0.24, 'maxAngularSpeed': 0.77, 'trackOffsetDeadband': 0.11},
            active_profile_name='自定义',
            runtime_param_version=4,
            reason='apply_param_profile:室内保守',
            ts='2026-04-01T00:00:00Z',
        )
    )
    DecisionNode.on_runtime_params(node, msg)
    assert node.track_manager.max_linear == 0.24
    assert node.track_manager.max_angular == 0.77
    assert node.track_manager.offset_deadband == 0.11
