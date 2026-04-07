from __future__ import annotations

import sys
import threading
import time
from types import ModuleType


def _install_ros_stubs() -> None:
    if 'rclpy' not in sys.modules:
        rclpy = ModuleType('rclpy')
        rclpy.ok = lambda: True
        sys.modules['rclpy'] = rclpy
    if 'rclpy.node' not in sys.modules:
        node_mod = ModuleType('rclpy.node')

        class Node:
            pass

        node_mod.Node = Node
        sys.modules['rclpy.node'] = node_mod


_install_ros_stubs()

import robot_decision.action_runtime as action_runtime_module
from robot_decision.action_runtime import ActionRuntime
from robot_decision.decision_node import DecisionNode
from robot_utils.constants import MODE_TRACK


class _GoalHandle:
    def __init__(self) -> None:
        self.request = type('Request', (), {'min_confidence': 0.0, 'requested_by': 'test', 'reason': 'track', 'trace_id': 'trace-track'})()
        self.is_cancel_requested = False
        self.feedback = []
        self.status = None

    def publish_feedback(self, feedback) -> None:
        self.feedback.append(feedback)

    def succeed(self) -> None:
        self.status = 'succeeded'

    def abort(self) -> None:
        self.status = 'aborted'

    def canceled(self) -> None:
        self.status = 'canceled'


class _TrackAction:
    class Result:
        def __init__(self) -> None:
            self.success = False
            self.message = ''
            self.trace_id = ''
            self.final_mode = ''
            self.lost_target_count = 0

    class Feedback:
        def __init__(self) -> None:
            self.target_detected = False
            self.target_type = ''
            self.confidence = 0.0
            self.offset_x = 0.0
            self.offset_y = 0.0
            self.lost_target_count = 0
            self.message = ''
            self.trace_id = ''


class _Node:
    def __init__(self) -> None:
        self._actions = {'TrackTarget': _TrackAction}
        self._action_lock = threading.RLock()
        self._active_track_goal = None
        self.current_mode = MODE_TRACK
        self.context = type('Context', (), {
            'lost_target_count': 0,
            'active_action_message': 'tracking',
            'last_target_type': '',
        })()
        self.track_manager = type('TrackManager', (), {'min_confidence': 0.0})()
        self.last_target = None

    def request_mode_change(self, mode: str, requested_by: str, reason: str):
        return True, 'ok'


def test_action_runtime_shutdown_releases_waiting_executor(monkeypatch) -> None:
    monkeypatch.setattr(action_runtime_module.rclpy, 'ok', lambda: True)
    node = _Node()
    runtime = ActionRuntime(node)
    goal_handle = _GoalHandle()
    result_holder = {}

    worker = threading.Thread(target=lambda: result_holder.setdefault('result', runtime.execute_track_target(goal_handle)))
    worker.start()
    time.sleep(0.05)
    runtime.notify_shutdown()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    result = result_holder['result']
    assert result.success is False
    assert result.message == 'ROS shutdown'
    assert goal_handle.status == 'aborted'
    assert result.trace_id == 'trace-track'


def test_decision_cancel_callback_notifies_action_runtime() -> None:
    calls = []
    node = type('NodeStub', (), {'notify_state_change': lambda self: calls.append('notified')})()

    response = DecisionNode.on_action_cancel(node, object())

    assert calls == ['notified']
    assert response is True


def test_decision_destroy_node_notifies_shutdown() -> None:
    calls = []
    action_runtime = type('RuntimeStub', (), {'notify_shutdown': lambda self: calls.append('shutdown')})()
    node = type('NodeStub', (), {'action_runtime': action_runtime})()

    result = DecisionNode.destroy_node(node)

    assert calls == ['shutdown']
    assert result is True
