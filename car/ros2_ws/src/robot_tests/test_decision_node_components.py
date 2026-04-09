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


_install_ros_stubs()

from robot_decision.decision_node import DecisionNode


def test_decision_node_requires_real_components() -> None:
    node = object.__new__(DecisionNode)
    try:
        node._mode_guard()
    except RuntimeError as exc:
        assert 'mode_guard' in str(exc)
    else:
        raise AssertionError('missing component should fail fast')


def test_decision_node_rejects_wrong_app_service_type() -> None:
    node = object.__new__(DecisionNode)
    node.app_service = object()
    try:
        node._app_service()
    except RuntimeError as exc:
        assert 'app_service' in str(exc)
    else:
        raise AssertionError('unexpected app_service type should fail fast')
