from __future__ import annotations

import json
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

import robot_control.control_node as control_node_module
from geometry_msgs.msg import Twist
from robot_control.control_node import ControlNode


class _Publisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, msg) -> None:
        self.messages.append(msg)


class _FakeNode:
    def __init__(self) -> None:
        self.mode = 'IDLE'
        self.manual_cmd = object()
        self.patrol_cmd = object()
        self.track_cmd = object()
        self.navigation_cmd = object()
        self.last_fault = None
        self.fault_hold_until = 0.0
        self.chassis_state = SimpleNamespace(comm_ok=True, heartbeat_ok=True)
        self.chassis_state_at = 9.9
        self.power_state = SimpleNamespace(low_power_warn=False, low_power_stop=False)
        self.power_state_at = 0.0
        self.last_output = Twist()
        self.selection = SimpleNamespace()
        self.runtime_param_overrides = {}
        self.pub = _Publisher()
        self.source_pub = _Publisher()
        self.summary_pub = _Publisher()
        self._params = {
            'manual_timeout_sec': 0.6,
            'patrol_timeout_sec': 0.8,
            'track_timeout_sec': 0.5,
            'max_linear': 0.3,
            'max_angular': 1.2,
            'reverse_max_linear': 0.18,
            'turn_slowdown_ratio': 0.5,
            'track_linear_scale': 0.7,
            'track_angular_scale': 0.85,
            'resume_linear_step': 0.03,
            'max_linear_step': 0.05,
            'resume_angular_step': 0.08,
            'max_angular_step': 0.12,
            'chassis_timeout_sec': 0.8,
            'power_timeout_sec': 2.0,
            'low_power_linear_scale': 0.5,
            'low_power_angular_scale': 0.8,
        }

    def get_parameter(self, name: str):
        return SimpleNamespace(value=self._params[name])

    def _runtime_param_value(self, key: str, fallback: float) -> float:
        return ControlNode._runtime_param_value(self, key, fallback)


def test_control_node_passes_power_timeout_state(monkeypatch) -> None:
    fake = _FakeNode()
    cmd = Twist()
    cmd.linear.x = 0.2
    cmd.angular.z = 0.1

    monkeypatch.setattr(control_node_module, 'select_command_with_audit', lambda *args, **kwargs: ('manual', cmd, {'selectedSource': 'manual', 'selectedAgeSec': 0.05, 'sources': {}}))
    monkeypatch.setattr(control_node_module, 'source_age_sec', lambda *_args, **_kwargs: 0.05)
    monkeypatch.setattr(control_node_module, 'limit_twist', lambda selected, **_kwargs: selected)
    monkeypatch.setattr(control_node_module, 'apply_ramp', lambda _last, limited, **_kwargs: limited)
    monkeypatch.setattr(control_node_module, 'apply_safety', lambda ramped, *_args, **_kwargs: (ramped, False, 'ok'))
    monkeypatch.setattr(control_node_module, 'monotonic_time', lambda: 10.0)
    monkeypatch.setattr(control_node_module, 'safe_json_dumps', lambda payload: json.dumps(payload, ensure_ascii=False))

    captured = {}

    def _fake_power_guard(_cmd, _power_state, *_args, **kwargs):
        captured['power_state_stale'] = kwargs.get('power_state_stale')
        out = Twist()
        out.linear.x = 0.0
        out.angular.z = 0.0
        return out, True, 'power_state_stale'

    monkeypatch.setattr(control_node_module, 'apply_power_guard', _fake_power_guard)

    ControlNode.publish_final_cmd(fake)

    assert captured['power_state_stale'] is True
    summary = json.loads(fake.summary_pub.messages[-1].data)
    assert summary['power_reason'] == 'power_state_stale'
    assert summary['power_age_sec'] is None
