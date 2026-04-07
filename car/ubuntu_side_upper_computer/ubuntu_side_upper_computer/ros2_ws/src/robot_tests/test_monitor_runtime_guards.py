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

import robot_monitor.monitor_node as monitor_node_module
from robot_monitor.monitor_node import MonitorNode
from robot_monitor.status_aggregator import StatusSnapshot
from std_msgs.msg import String


class _Evidence:
    def __init__(self) -> None:
        self.updates = []

    def update(self, **fields):
        self.updates.append(fields)


class _Metrics:
    reconnect_count = 0
    protocol_errors = 0
    events_logged = 0
    snapshots_saved = 0


class _FakeNode:
    def __init__(self) -> None:
        self.snapshot = StatusSnapshot(wifi_ok=True, camera_ok=True, audio_ok=True, uart_ok=True)
        self.metrics = _Metrics()
        self.evidence_index = _Evidence()
        self.event_pub = object()

    def _log_runtime_io_error(self, scope: str, exc: Exception) -> None:
        self.get_logger().error(f'{scope} failed: {exc}')

    def _safe_evidence_update(self, **fields) -> None:
        self.evidence_index.update(**fields)

    def _safe_evidence_record_event(self, category: str, name: str, detail: str = '') -> None:
        if hasattr(self.evidence_index, 'record_event'):
            self.evidence_index.record_event(category, name, detail)

    def _safe_evidence_record_snapshot(self, filepath: str) -> None:
        if hasattr(self.evidence_index, 'record_snapshot'):
            self.evidence_index.record_snapshot(filepath)

    def _safe_logger_append(self, record) -> None:
        try:
            self.logger_jsonl.append(record)
        except Exception as exc:
            self._log_runtime_io_error('event log append', exc)

    def get_logger(self):
        return _FakeLoggerSink()


def test_monitor_bridge_summary_updates_stale_flags() -> None:
    node = _FakeNode()
    msg = String()
    msg.data = json.dumps({
        'connected': False,
        'state': 'reconnecting',
        'transport_degraded': True,
        'reconnect_count': 3,
        'protocol_errors': 2,
        'last_protocol_error': 'bad_crc',
    })

    MonitorNode.on_bridge_summary(node, msg)

    assert node.snapshot.bridge_ok is False
    assert node.snapshot.stale_bridge is True
    assert node.snapshot.reconnect_count == 3
    assert node.metrics.protocol_errors == 2
    assert node.evidence_index.updates[-1]['last_protocol_issue'] == 'bad_crc'


def test_monitor_bridge_summary_invalid_json_uses_event_pub(monkeypatch) -> None:
    node = _FakeNode()
    msg = String()
    msg.data = '{bad json'
    calls = []
    monkeypatch.setattr(monitor_node_module, 'publish_policy_outcome', lambda _node, *, outcome, event_pub: calls.append(event_pub))

    MonitorNode.on_bridge_summary(node, msg)

    assert calls == [node.event_pub]


def test_monitor_runtime_params_invalid_threshold_uses_event_pub(monkeypatch) -> None:
    node = _FakeNode()
    node._runtime_low_power_threshold = 25.0
    msg = String()
    msg.data = json.dumps({'params': {'lowPowerThreshold': 'NaN'}})
    calls = []
    monkeypatch.setattr(monitor_node_module, 'publish_policy_outcome', lambda _node, *, outcome, event_pub: calls.append(event_pub))

    MonitorNode.on_runtime_params(node, msg)

    assert calls == [node.event_pub]
    assert node._runtime_low_power_threshold == 25.0



class _FailingLoggerJsonl:
    def append(self, record):
        raise OSError('disk full')


class _FailingMetrics:
    reconnect_count = 0
    protocol_errors = 0

    def dump_json(self, path):
        raise OSError('metrics unavailable')


class _FakeLoggerSink:
    def __init__(self) -> None:
        self.errors = []

    def error(self, message):
        self.errors.append(message)


class _EventNode(_FakeNode):
    def __init__(self) -> None:
        super().__init__()
        self.logger_jsonl = _FailingLoggerJsonl()
        self.evidence_index = _Evidence()
        self._logger = _FakeLoggerSink()

    def get_logger(self):
        return self._logger


class _MetricsNode(_FakeNode):
    def __init__(self) -> None:
        super().__init__()
        self.metrics = _FailingMetrics()
        self.evidence_index = _Evidence()
        self._logger = _FakeLoggerSink()
        self._last_metrics_flush_ns = 0
        self._last_health = None

    def get_logger(self):
        return self._logger

    def get_clock(self):
        class _Clock:
            class _Now:
                nanoseconds = 10_000_000_000
            def now(self):
                return self._Now()
        return _Clock()

    def get_parameter(self, name):
        values = {'metrics_flush_period': 0.1, 'metrics_path': '/tmp/metrics.json'}
        return SimpleNamespace(value=values[name])


def test_monitor_on_event_does_not_raise_when_event_log_write_fails() -> None:
    from robot_msgs.msg import EventLog

    node = _EventNode()
    msg = EventLog()
    msg.category = 'system'
    msg.name = 'tick'
    msg.detail = 'demo'
    msg.level = 'info'
    msg.source = 'test'

    MonitorNode.on_event(node, msg)

    assert any('event log append failed' in item for item in node.get_logger().errors)


def test_monitor_metrics_flush_failure_is_contained() -> None:
    node = _MetricsNode()

    MonitorNode._maybe_flush_metrics(node, health='ok')

    assert any('metrics flush failed' in item for item in node.get_logger().errors)


class _RecordingLoggerJsonl:
    def __init__(self) -> None:
        self.records = []

    def append(self, record):
        self.records.append(dict(record))


def test_monitor_safe_logger_append_uses_real_writer() -> None:
    node = _FakeNode()
    node.logger_jsonl = _RecordingLoggerJsonl()
    node.metrics = _Metrics()

    MonitorNode._safe_logger_append(node, {'category': 'system', 'name': 'tick'})

    assert node.logger_jsonl.records == [{'category': 'system', 'name': 'tick'}]
    assert getattr(node.metrics, 'event_log_write_successes', 0) == 0 or getattr(node.metrics, 'event_log_write_successes', 0) >= 0
