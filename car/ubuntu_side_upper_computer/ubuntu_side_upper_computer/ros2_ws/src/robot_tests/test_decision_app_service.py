from __future__ import annotations

import threading
from types import SimpleNamespace

from std_msgs.msg import String
from robot_contracts.runtime_param_transport import build_runtime_param_payload, dumps_runtime_param_payload
from robot_decision.decision_app_service import DecisionAppService
from robot_decision.decision_ingress import DecisionIngress
from robot_decision.decision_policy import DecisionPolicy
from robot_decision.decision_side_effects import DecisionSideEffects
from robot_decision.decision_state_controller import DecisionStateController
from robot_decision.mission_context import MissionContext
from robot_decision.mission_orchestrator import MissionOrchestrator
from robot_decision.mode_guard import ModeGuard
from robot_decision.runtime_param_adapter import RuntimeParamAdapter
from robot_decision.track_manager import TrackManager
from robot_utils.constants import MODE_BOOT


class _Publisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, msg) -> None:
        self.messages.append(msg)


class _Param:
    def __init__(self, value):
        self.value = value


class _Clock:
    class _Now:
        def __init__(self) -> None:
            self.nanoseconds = 0

        def to_msg(self):
            from builtin_interfaces.msg import Time
            return Time()

    def now(self):
        return self._Now()


class _PatrolManager:
    def __init__(self) -> None:
        self.current_index = 0

    def manual_interrupt_allowed(self) -> bool:
        return True

    def reset(self, now_sec: float) -> None:
        self.current_index = 0

    def note_detection(self, *, target_type: str, confidence: float) -> None:
        del target_type, confidence

    def step_descriptor(self):
        return {'retry_count': 0, 'retry_limit': 0}

    def progress_ratio(self, now_sec: float) -> float:
        del now_sec
        return 0.0

    def update(self, now_sec: float):
        raise AssertionError('tick not expected in this test')

    def is_finished(self) -> bool:
        return False


class _BootTimer:
    def cancel(self) -> None:
        return None


class _Node:
    def __init__(self) -> None:
        self.current_mode = MODE_BOOT
        self.previous_mode = MODE_BOOT
        self.last_fault = None
        self.system_status = None
        self.chassis_state = None
        self.last_target = None
        self.context = MissionContext()
        self._state_lock = threading.RLock()
        self._safe_stop_manual_confirmed = False
        self._runtime_param_overrides = {}
        self.track_manager = TrackManager(min_confidence=0.0)
        self.patrol_manager = _PatrolManager()
        self.mode_pub = _Publisher()
        self.event_pub = _Publisher()
        self.patrol_pub = _Publisher()
        self.track_pub = _Publisher()
        self.speak_pub = _Publisher()
        self.snapshot_pub = _Publisher()
        self.summary_pub = _Publisher()
        self.runtime_param_apply_pub = _Publisher()
        self.action_runtime = SimpleNamespace(notify_state_change=lambda: None)
        self.boot_timer = _BootTimer()
        self._params = {
            'decision_intent_queue_max': 8,
            'decision_intent_batch_max': 4,
            'decision_intent_sync_timeout_sec': 0.05,
            'snapshot_on_fault': True,
            'auto_track_on_target': True,
            'target_confidence_min': 0.55,
            'track_lost_limit': 3,
            'snapshot_on_target': True,
            'snapshot_on_qrcode': True,
            'safe_stop_on_wifi_loss': True,
            'require_ready_for_patrol': True,
            'patrol_config_path': '',
            'strict_patrol_config': False,
            'allow_default_patrol_fallback': True,
            'patrol_step_duration': 2.5,
        }

    def get_parameter(self, name: str):
        return _Param(self._params[name])

    def get_clock(self):
        return _Clock()

    def state_guard(self):
        class _Guard:
            def __init__(self, lock):
                self._lock = lock
            def __enter__(self):
                self._lock.acquire()
                return None
            def __exit__(self, exc_type, exc, tb):
                self._lock.release()
                return False
        return _Guard(self._state_lock)

    def _run_state_mutation(self, description, mutation):
        del description
        with self.state_guard():
            return mutation()

    def _set_mode_locked(self, new_mode: str, requested_by: str, reason: str) -> None:
        del requested_by
        if new_mode == self.current_mode:
            return
        self.previous_mode = self.current_mode
        self.current_mode = new_mode
        self.context.last_transition_reason = reason
        if new_mode != 'TRACK':
            self.context.lost_target_count = 0


def _build_service(node: _Node) -> DecisionAppService:
    mode_guard = ModeGuard(node)
    state_controller = DecisionStateController(node=node)
    side_effects = DecisionSideEffects(node=node)
    return DecisionAppService(
        node=node,
        ingress=DecisionIngress(),
        policy=DecisionPolicy(node=node),
        state_controller=state_controller,
        side_effects=side_effects,
        mission_orchestrator=MissionOrchestrator(node=node),
        runtime_adapter=RuntimeParamAdapter(node),
        mode_guard=mode_guard,
    )


def test_app_service_complete_boot_transitions_to_idle_and_speaks(monkeypatch) -> None:
    monkeypatch.setattr('robot_decision.decision_projection.command_capability_snapshot', lambda ctx: {'allowedTargetModes': [], 'modeReasons': {}, 'commandPermissions': {}})
    node = _Node()
    service = _build_service(node)
    service.complete_boot()
    assert node.current_mode == 'IDLE'
    assert node.speak_pub.messages


def test_app_service_runtime_params_apply_updates_track_manager(monkeypatch) -> None:
    monkeypatch.setattr('robot_decision.decision_projection.command_capability_snapshot', lambda ctx: {'allowedTargetModes': [], 'modeReasons': {}, 'commandPermissions': {}})
    node = _Node()
    service = _build_service(node)
    msg = String()
    msg.data = dumps_runtime_param_payload(
        build_runtime_param_payload(
            {'maxLinearSpeed': 0.33, 'maxAngularSpeed': 1.2, 'trackOffsetDeadband': 0.07},
            active_profile_name='自定义',
            runtime_param_version=2,
            reason='test',
            ts='2026-04-04T00:00:00Z',
            transaction_id='txn-2',
        )
    )
    service.on_runtime_params(msg)
    assert node.track_manager.max_linear == 0.33
    assert node.track_manager.max_angular == 1.2
    assert node.track_manager.offset_deadband == 0.07
    assert node.runtime_param_apply_pub.messages


def test_state_controller_compat_wrapper_delegates_to_app_service() -> None:
    node = _Node()
    state_controller = DecisionStateController(node=node)
    calls = []

    class _AppService:
        def dispatch_intent(self, kind, payload=None):
            calls.append((kind, payload))
            return 'delegated-result'

    node.app_service = _AppService()
    result = state_controller.resolve_intent('fault', {'code': 'E1'})

    assert result == 'delegated-result'
    assert calls == [('fault', {'code': 'E1'})]
    assert node.last_fault is None
