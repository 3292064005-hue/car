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


class _FakeActionClient:
    def __init__(self, node, action_type, name):
        self.node = node
        self.action_type = action_type
        self.name = name
        self.wait_calls = 0
        self.goal_futures = []
        self.sent_goals = []

    def wait_for_server(self, timeout_sec: float) -> bool:
        self.wait_calls += 1
        return True

    def send_goal_async(self, goal, feedback_callback=None):
        self.sent_goals.append((goal, feedback_callback))
        future = _FakeFuture()
        self.goal_futures.append(future)
        return future


class _FakeModeClient:
    def __init__(self):
        self.calls = 0
        self.requests = []

    def wait_for_service(self, timeout_sec: float) -> bool:
        return True

    def call_async(self, req):
        self.calls += 1
        self.requests.append(req)
        return _FakeFuture()


class _FakePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, msg):
        self.messages.append(msg)


class _FakeLogger:
    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class _FakeNode:
    def __init__(self):
        self.mode_client = _FakeModeClient()
        self.reset_client = _FakeModeClient()
        self.snapshot_client = _FakeModeClient()
        self.manual_pub = _FakePublisher()
        self.speak_pub = _FakePublisher()
        self.state = SimpleNamespace(task={})
        self.envelopes = SimpleNamespace(event=lambda event_type, payload, source='ros2', trace_id=None: {'type': event_type, 'payload': payload, 'source': source, 'traceId': trace_id})
        self.sent_acks = []
        self.audit = []
        self.sent_events = []

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

    def send_ack(self, event_id, status, message, *, detail='', trace_id='', lifecycle_status='', lifecycle_phase=''):
        self.sent_acks.append((event_id, status, message, detail, trace_id, lifecycle_status, lifecycle_phase))

    def _sync_snapshot_cache(self):
        pass

    def schedule_send(self, envelope):
        self.sent_events.append(envelope)

    def now_iso(self):
        return '2026-04-01T00:00:00Z'

    def apply_runtime_param_update(self, **kwargs):
        raise AssertionError('not expected')

    def apply_runtime_param_profile(self, **kwargs):
        raise AssertionError('not expected')

    def apply_runtime_param_draft(self, **kwargs):
        raise AssertionError('not expected')

    def get_logger(self):
        return _FakeLogger()


class _StartPatrol:
    class Goal:
        def __init__(self):
            self.requested_by = ''
            self.reason = ''
            self.mission_id = ''
            self.route_name = ''
            self.task_profile = ''
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


class _GoalHandle:
    accepted = True

    def get_result_async(self):
        return _FakeFuture()


def test_set_mode_track_bridges_to_track_action_from_patrol(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    node.build_command_context = lambda: CommandContext(
        current_mode='PATROL',
        bridge_connected=True,
        low_power_warning=False,
        fault_code=None,
        fault_level='info',
        estop_active=False,
        safe_stop_active=False,
        safe_stop_recoverable=True,
        safe_stop_blocked_reason=None,
    )
    router = CommandRouter(node)

    router.handle({'type': 'set_mode', 'event_id': 'evt-1', 'payload': {'mode': 'TRACK', 'targetType': 'person', 'minConfidence': 0.7}, 'reason': 'track', 'operator_id': 'tester'})

    assert node.mode_client.calls == 0
    assert len(router.track_action_client.sent_goals) == 1
    goal, _feedback_cb = router.track_action_client.sent_goals[0]
    assert goal.target_type == 'person'
    assert goal.min_confidence == 0.7
    assert node.state.task['actionName'] == 'track_target'
    assert node.state.task['actionPhase'] == 'queued'


def test_set_mode_track_is_denied_from_idle(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    router = CommandRouter(node)

    router.handle({'type': 'set_mode', 'event_id': 'evt-track-deny', 'payload': {'mode': 'TRACK', 'targetType': 'person'}, 'reason': 'track', 'operator_id': 'tester'})

    assert node.mode_client.calls == 0
    assert router.track_action_client is not None
    assert router.track_action_client.sent_goals == []
    assert any(item[0] == 'evt-track-deny' and item[5] == 'denied' for item in node.sent_acks)


def test_patrol_goal_acceptance_updates_ack_and_task(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    router = CommandRouter(node)

    router.handle({'type': 'start_patrol', 'event_id': 'evt-2', 'payload': {}, 'reason': 'patrol', 'operator_id': 'tester'})
    future = router.patrol_action_client.goal_futures[0]
    future.result = lambda: _GoalHandle()
    router.on_patrol_goal_response(future)

    assert any(item[0] == 'evt-2' and item[1] == 'ack' and item[5] == 'accepted' and item[6] == 'ros_accepted' for item in node.sent_acks)
    assert node.state.task['actionName'] == 'start_patrol'
    assert node.state.task['actionPhase'] == 'accepted'
    assert node.state.task['patrolStatus'] == 'running'


class _CancelableGoalHandle(_GoalHandle):
    def __init__(self):
        self.cancelled = False

    def cancel_goal_async(self):
        self.cancelled = True
        return _FakeFuture()


def test_pause_patrol_requests_action_cancel_and_task_feedback(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    node.build_command_context = lambda: CommandContext(
        current_mode='PATROL',
        bridge_connected=True,
        low_power_warning=False,
        fault_code=None,
        fault_level='info',
        estop_active=False,
        safe_stop_active=False,
        safe_stop_recoverable=True,
        safe_stop_blocked_reason=None,
    )
    router = CommandRouter(node)
    goal = _CancelableGoalHandle()
    router.active_patrol_goal = goal

    router.handle({'type': 'pause_patrol', 'event_id': 'evt-3', 'payload': {}, 'reason': 'pause', 'operator_id': 'tester'})

    assert goal.cancelled is True
    assert node.mode_client.calls == 1
    assert node.state.task['actionPhase'] == 'cancelling'
    assert node.state.task['patrolStatus'] == 'paused'



def test_set_mode_track_preserves_trace_id_on_ack(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    router = CommandRouter(node)

    router.handle({'type': 'start_patrol', 'event_id': 'evt-trace', 'trace_id': 'trace-123', 'payload': {}, 'reason': 'patrol', 'operator_id': 'tester'})
    future = router.patrol_action_client.goal_futures[0]
    future.result = lambda: _GoalHandle()
    router.on_patrol_goal_response(future)

    assert any(item[0] == 'evt-trace' and item[4] == 'trace-123' for item in node.sent_acks)



def test_set_mode_done_preserves_trace_id_in_task_event(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    router = CommandRouter(node)

    pending = command_router_module.PendingAck(event_id='evt-mode', command_type='resume_from_safe_stop', requested_mode='IDLE', trace_id='trace-mode')
    future = _FakeFuture()
    router.pending_mode_acks[future] = pending
    future.result = lambda: SimpleNamespace(success=True, message='mode changed')

    router.on_set_mode_done(future)

    assert node.sent_events[-1]['traceId'] == 'trace-mode'


def test_set_mode_service_request_preserves_trace_id(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    router = CommandRouter(node)

    router.handle({'type': 'set_mode', 'event_id': 'evt-service-trace', 'trace_id': 'trace-service', 'payload': {'mode': 'MANUAL'}, 'reason': 'idle', 'operator_id': 'tester'})

    assert node.mode_client.requests[-1].trace_id == 'trace-service'


def test_start_patrol_goal_preserves_trace_id(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    router = CommandRouter(node)

    router.handle({'type': 'start_patrol', 'event_id': 'evt-goal-trace', 'trace_id': 'trace-goal', 'payload': {}, 'reason': 'patrol', 'operator_id': 'tester'})

    goal, _feedback_cb = router.patrol_action_client.sent_goals[0]
    assert goal.trace_id == 'trace-goal'


def test_apply_param_draft_dispatches_one_backend_call(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    calls = []
    node.apply_runtime_param_draft = lambda **kwargs: calls.append(kwargs) or 'ok'
    router = CommandRouter(node)

    router.handle({'type': 'apply_param_draft', 'event_id': 'evt-draft', 'trace_id': 'trace-draft', 'payload': {'params': {'maxLinearSpeed': 0.5, 'maxAngularSpeed': 1.1, 'teleopStep': 0.08, 'trackOffsetDeadband': 0.1, 'lowPowerThreshold': 25, 'reconnectTimeoutMs': 1500}}, 'reason': 'frontend', 'operator_id': 'tester'})

    assert len(calls) == 1
    assert calls[0]['command_type'] == 'apply_param_draft'
    assert calls[0]['trace_id'] == 'trace-draft'
    assert any(item[0] == 'evt-draft' and item[5] == 'completed' and item[6] == 'business_completed' for item in node.sent_acks)



def test_start_patrol_goal_propagates_product_mission_payload(monkeypatch):
    monkeypatch.setattr(command_router_module, 'ActionClient', _FakeActionClient)
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {
        'StartPatrol': _StartPatrol,
        'TrackTarget': _TrackTarget,
        'SaveSnapshotTask': _SaveSnapshotTask,
    })
    node = _FakeNode()
    router = CommandRouter(node)

    router.handle({'type': 'start_patrol', 'event_id': 'evt-mission', 'trace_id': 'trace-mission', 'payload': {'missionId': 'dock_then_patrol', 'routeName': 'dock_loop', 'taskProfile': 'dock_patrol'}, 'reason': 'patrol', 'operator_id': 'tester'})

    goal, _feedback_cb = router.patrol_action_client.sent_goals[0]
    assert goal.mission_id == 'dock_then_patrol'
    assert goal.route_name == 'dock_loop'
    assert goal.task_profile == 'dock_patrol'
    assert goal.trace_id == 'trace-mission'


def test_speak_fixed_text_publishes_strict_speak_request_topic(monkeypatch):
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {})
    node = _FakeNode()
    router = CommandRouter(node)

    router.handle({
        'type': 'speak_fixed_text',
        'event_id': 'evt-speak',
        'payload': {'text': '系统状态正常', 'priority': 3},
        'reason': 'operator_voice',
        'operator_id': 'tester',
        'trace_id': 'trace-speak',
    })

    assert node.speak_pub.messages
    msg = node.speak_pub.messages[0]
    assert msg.text_id == '系统状态正常'
    assert msg.priority == 3
    assert msg.requested_by == 'tester'
    assert msg.trace_id == 'trace-speak'
    assert node.sent_acks[-1][1] == 'ack'
    assert node.sent_acks[-1][5] == 'applied'


def test_speak_fixed_text_rejects_empty_text_without_publishing(monkeypatch):
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {})
    node = _FakeNode()
    router = CommandRouter(node)

    router.handle({
        'type': 'speak_fixed_text',
        'event_id': 'evt-speak-empty',
        'payload': {'text': '   '},
        'reason': 'operator_voice',
        'operator_id': 'tester',
    })

    assert node.speak_pub.messages == []
    assert node.sent_acks[-1][1] == 'rejected'
    assert node.sent_acks[-1][3] == 'empty_speak_text'


def test_save_snapshot_service_fallback_uses_declared_srv_fields(monkeypatch):
    monkeypatch.setattr(command_router_module, 'load_robot_actions', lambda: {})
    node = _FakeNode()
    router = CommandRouter(node)

    router.handle({
        'type': 'save_snapshot',
        'event_id': 'evt-snapshot',
        'payload': {'filename': 'ignored-by-contract.jpg', 'reason': 'manual_capture'},
        'reason': 'manual_snapshot',
        'operator_id': 'tester',
        'trace_id': 'trace-snapshot',
    })

    assert node.snapshot_client.calls == 1
    req = node.snapshot_client.requests[0]
    assert req.reason == 'manual_capture'
    assert req.trace_id == 'trace-snapshot'
    assert not hasattr(req, 'filename')
    assert node.audit[-1][:3] == ('evt-snapshot', 'save_snapshot', 'queued')

