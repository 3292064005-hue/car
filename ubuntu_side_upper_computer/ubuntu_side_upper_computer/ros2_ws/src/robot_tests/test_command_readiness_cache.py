from __future__ import annotations

from types import SimpleNamespace

from robot_contracts.bridge_contract import CommandContext
from robot_web_bridge.command_router import CommandRouter


class _FakeFuture:
    def __init__(self):
        self.callbacks = []

    def add_done_callback(self, cb):
        self.callbacks.append(cb)


class _FakeClient:
    def __init__(self):
        self.wait_calls = 0
        self.call_calls = 0

    def wait_for_service(self, timeout_sec: float) -> bool:
        self.wait_calls += 1
        return True

    def call_async(self, req):
        self.call_calls += 1
        return _FakeFuture()


class _FakePublisher:
    def publish(self, msg):
        pass


class _FakeLogger:
    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class _FakeReadiness:
    def __init__(self, values):
        self.values = dict(values)

    def is_ready(self, name: str) -> bool:
        return bool(self.values.get(name, False))


class _FakeNode:
    def __init__(self):
        self.mode_client = _FakeClient()
        self.reset_client = _FakeClient()
        self.snapshot_client = _FakeClient()
        self.manual_pub = _FakePublisher()
        self.speak_pub = _FakePublisher()
        self.state = SimpleNamespace(task={})
        self.readiness_cache = _FakeReadiness({
            '/robot/set_mode': True,
            '/robot/reset_fault': True,
            '/robot/save_snapshot': True,
        })

    def build_command_context(self):
        return CommandContext(
            current_mode='IDLE',
            bridge_connected=True,
            low_power_warning=False,
            fault_code=None,
            fault_level='info',
            estop_active=False,
            safe_stop_active=False,
            safe_stop_recoverable=True,
            safe_stop_blocked_reason=None,
        )

    def audit_command(self, *args, **kwargs):
        pass

    def send_ack(self, *args, **kwargs):
        pass

    def apply_runtime_param_update(self, **kwargs):
        return 'ok'

    def apply_runtime_param_profile(self, **kwargs):
        return 'ok'

    def broadcast_snapshot(self):
        pass

    def get_logger(self):
        return _FakeLogger()


def test_mode_command_uses_readiness_cache_without_waiting(monkeypatch):
    monkeypatch.setattr('robot_web_bridge.command_router.load_robot_actions', lambda: {})
    node = _FakeNode()
    router = CommandRouter(node)

    router.handle({'type': 'set_mode', 'event_id': 'evt-1', 'payload': {'mode': 'MANUAL'}})

    assert node.mode_client.wait_calls == 0
    assert node.mode_client.call_calls == 1
