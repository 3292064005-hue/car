from __future__ import annotations

import asyncio
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

from robot_web_bridge.web_bridge_node import RobotWebBridgeNode


class _Dispatcher:
    def __init__(self) -> None:
        self.items = []

    def enqueue(self, item) -> None:
        self.items.append(item)


class _FakeNode:
    def __init__(self) -> None:
        self.state = SimpleNamespace(last_trace_id=None)
        self.dispatcher = _Dispatcher()
        self.sent_acks = []
        self.audit = []
        self.event_pub = SimpleNamespace(publish=lambda *a, **k: None)
        self._logger = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None)
        self._clock = SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: SimpleNamespace()))

    def audit_command(self, event_id, command_type, status, message):
        self.audit.append((event_id, command_type, status, message))

    def send_ack(self, event_id, status, message, *, detail='', trace_id='', lifecycle_status=''):
        self.sent_acks.append((event_id, status, message, detail, trace_id, lifecycle_status))

    def get_logger(self):
        return self._logger

    def get_name(self):
        return 'robot_web_bridge'

    def get_clock(self):
        return self._clock


async def _run_invalid_command(node: _FakeNode) -> None:
    payload = json.dumps({'eventId': 'evt-1', 'type': 'unknown_cmd', 'traceId': 'trace-xyz', 'payload': {}})
    await RobotWebBridgeNode.handle_ws_message(node, payload)


async def _run_invalid_payload(node: _FakeNode) -> None:
    payload = json.dumps({'eventId': 'evt-2', 'type': 'set_mode', 'traceId': 'trace-bad-payload', 'payload': []})
    await RobotWebBridgeNode.handle_ws_message(node, payload)


def test_invalid_command_ack_preserves_trace_id() -> None:
    node = _FakeNode()
    asyncio.run(_run_invalid_command(node))
    assert node.state.last_trace_id == 'trace-xyz'
    assert node.sent_acks == [('evt-1', 'denied', 'unsupported command type: unknown_cmd', '', 'trace-xyz', '')]
    assert node.dispatcher.items == []


def test_invalid_payload_shape_is_rejected_before_dispatch() -> None:
    node = _FakeNode()
    asyncio.run(_run_invalid_payload(node))
    assert node.state.last_trace_id == 'trace-bad-payload'
    assert node.sent_acks == [
        ('evt-2', 'denied', 'malformed command envelope: payload must be an object when present', '', 'trace-bad-payload', '')
    ]
    assert node.dispatcher.items == []
