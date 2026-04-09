from __future__ import annotations

from types import SimpleNamespace

import robot_web_bridge.command_router as command_router_module
from robot_contracts.bridge_contract import CommandContext
from robot_web_bridge.command_router import CommandRouter


class _FakeFuture:
    def __init__(self):
        self.callbacks = []

    def add_done_callback(self, cb):
        self.callbacks.append(cb)


class _FakeModeClient:
    def __init__(self):
        self.requests = []

    def wait_for_service(self, timeout_sec: float) -> bool:
        return True

    def call_async(self, req):
        self.requests.append(req)
        return _FakeFuture()


class _FakeActionClient:
    def __init__(self, node, action_type, name):
        self.sent_goals = []

    def wait_for_server(self, timeout_sec: float) -> bool:
        return True

    def send_goal_async(self, goal, feedback_callback=None):
        future = _FakeFuture()
        self.sent_goals.append((goal, feedback_callback, future))
        return future


class _FakePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, msg):
        self.messages.append(msg)




class _CancelableGoalHandle:
    def __init__(self):
        self.accepted = True
        self.cancelled = False
        self._result_future = _FakeFuture()

    def get_result_async(self):
        return self._result_future

    def cancel_goal_async(self):
        self.cancelled = True
        return _FakeFuture()


class _FakeLogger:
    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class _StartPatrol:
    class Goal:
        def __init__(self):
            self.requested_by = ''
            self.reason = ''
            self.trace_id = ''


class _TrackTarget:
    class Goal:
        def __init__(self):
            self.requested_by = ''
            self.reason = ''
            self.trace_id = ''
            self.target_type = ''
            self.min_confidence = 0.0


class _SaveSnapshotTask:
    class Goal:
        def __init__(self):
            self.requested_by = ''
            self.reason = ''
            self.trace_id = ''


class _FakeNode:
    def __init__(self):
        self.mode_client = _FakeModeClient()
        self.reset_client = _FakeModeClient()
        self.snapshot_client = _FakeModeClient()
        self.manual_pub = _FakePublisher()
        self.speak_pub = _FakePublisher()
        self.state = SimpleNamespace(task={'actionProgress': 0.0})
        self.envelopes = SimpleNamespace(event=lambda event_type, payload, source='ros2', trace_id=None: {'type': event_type, 'payload': payload, 'source': source, 'traceId': trace_id})
        self.sent_acks = []
        self.audit = []
        self.sent_events = []
        self.phases = []

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

    def audit_command(self, event_id, command_type, status, message):
        self.audit.append((event_id, command_type, status, message))

    def send_ack(self, event_id, status, message, *, detail='', trace_id='', lifecycle_status=''):
        self.sent_acks.append((event_id, status, message, detail, trace_id, lifecycle_status))

    def record_command_phase(self, event_id, command_type, phase, status, message, *, trace_id='', extra=None):
        self.phases.append((event_id, command_type, phase, status, message, trace_id, extra))

    def _sync_snapshot_cache(self):
        pass

    def schedule_send(self, envelope):
        self.sent_events.append(envelope)

    def now_iso(self):
        return '2026-04-02T00:00:00Z'

    def apply_runtime_param_update(self, **kwargs):
        raise AssertionError('not expected')

    def apply_runtime_param_profile(self, **kwargs):
        raise AssertionError('not expected')

    def apply_runtime_param_draft(self, **kwargs):
        raise AssertionError('not expected')

    def get_logger(self):
        return _FakeLogger()


def test_service_timeout_generates_timeout_ack(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    router = CommandRouter(node, operation_timeout_sec=0.5, monotonic=lambda: 0.0)

    router.handle({'type': 'set_mode', 'event_id': 'evt-timeout', 'trace_id': 'trace-timeout', 'payload': {'mode': 'MANUAL'}, 'reason': 'idle', 'operator_id': 'tester'})
    expired = router.expire_pending(now_monotonic=1.0)

    assert expired == 1
    assert node.sent_acks[-1][1] == 'timeout'
    assert node.sent_acks[-1][4] == 'trace-timeout'
    assert node.sent_acks[-1][5] == 'timeout'
    assert node.phases[-1][2] == 'timeout'
    assert node.phases[-1][3] == 'timeout'


def test_action_goal_timeout_generates_timeout_task_event(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    router = CommandRouter(node, operation_timeout_sec=0.5, monotonic=lambda: 0.0)

    router.handle({'type': 'start_patrol', 'event_id': 'evt-action-timeout', 'trace_id': 'trace-action-timeout', 'payload': {}, 'reason': 'patrol', 'operator_id': 'tester'})
    expired = router.expire_pending(now_monotonic=1.0)

    assert expired == 1
    assert node.sent_acks[-1][1] == 'timeout'
    assert node.sent_acks[-1][5] == 'timeout'
    assert node.sent_events[-1]['type'] == 'task_event'
    assert node.sent_events[-1]['traceId'] == 'trace-action-timeout'
    assert node.state.task['actionPhase'] == 'timeout'
    assert node.phases[-1][2] == 'timeout'
    assert node.phases[-1][3] == 'timeout'


def test_action_result_timeout_requests_goal_cancel(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    router = CommandRouter(node, operation_timeout_sec=0.5, monotonic=lambda: 0.0)

    router.handle({'type': 'start_patrol', 'event_id': 'evt-action-result-timeout', 'trace_id': 'trace-action-result-timeout', 'payload': {}, 'reason': 'patrol', 'operator_id': 'tester'})
    goal_future = router.patrol_action_client.sent_goals[0][2]
    goal_handle = _CancelableGoalHandle()
    goal_future.result = lambda: goal_handle
    router.on_patrol_goal_response(goal_future)

    expired = router.expire_pending(now_monotonic=1.0)

    assert expired == 1
    assert goal_handle.cancelled is True
    assert node.sent_acks[-1][1] == 'timeout'
    assert node.sent_acks[-1][5] == 'timeout'
    assert node.state.task['actionPhase'] == 'timeout'
