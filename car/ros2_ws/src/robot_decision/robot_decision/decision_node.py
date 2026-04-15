from __future__ import annotations

"""ROS composition root for the decision runtime."""

import threading
from contextlib import contextmanager
from typing import Callable, Iterator, TypeVar

import rclpy
try:
    from rclpy.executors import MultiThreadedExecutor
except Exception:  # pragma: no cover - test stubs may not expose executors
    MultiThreadedExecutor = None
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String
from robot_msgs.msg import ChassisState, Fault, ModeState, SpeakRequest, SystemStatus, VisionTarget, VoiceCommand, EventLog
from robot_msgs.srv import ResetFault, SetMode
from robot_contracts.bridge_contract import CommandContext
from robot_contracts.runtime_param_transport import RUNTIME_PARAM_APPLY_RESULT_TOPIC, RUNTIME_PARAM_TOPIC
from robot_decision.action_runtime import ActionRuntime
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
from robot_decision.decision_runtime_surface import (
    app_service as resolve_app_service,
    mode_guard as resolve_mode_guard,
    runtime_adapter as resolve_runtime_adapter,
    side_effects as resolve_side_effects,
    state_controller as resolve_state_controller,
)
from robot_utils.action_support import load_robot_actions
from robot_utils.callback_groups import build_callback_groups, call_with_callback_group
from robot_utils.qos_profiles import qos_for
from robot_utils.constants import MODE_BOOT, MODE_IDLE, MODE_PATROL, MODE_SAFE_STOP, MODE_TRACK

try:
    from rclpy.action import ActionServer, CancelResponse, GoalResponse
except Exception:  # pragma: no cover - environments without ROS action runtime
    ActionServer = None
    CancelResponse = None
    GoalResponse = None


TState = TypeVar('TState')


class DecisionNode(Node):
    """Thin ROS node that delegates decision logic to application services."""

    def __init__(self, node_name: str = 'robot_decision') -> None:
        super().__init__(node_name)
        self.declare_parameter('boot_delay_sec', 1.0)
        self.declare_parameter('track_lost_limit', 8)
        self.declare_parameter('auto_track_on_target', True)
        self.declare_parameter('target_confidence_min', 0.55)
        self.declare_parameter('safe_stop_on_wifi_loss', True)
        self.declare_parameter('snapshot_on_qrcode', True)
        self.declare_parameter('snapshot_on_target', True)
        self.declare_parameter('snapshot_on_fault', True)
        self.declare_parameter('require_ready_for_patrol', True)
        self.declare_parameter('default_patrol_route', 'default')
        self.declare_parameter('decision_intent_queue_max', 128)
        self.declare_parameter('decision_intent_batch_max', 32)
        self.declare_parameter('decision_intent_sync_timeout_sec', 0.25)

        self.current_mode = MODE_BOOT
        self.previous_mode = MODE_BOOT
        self.last_fault: Fault | None = None
        self.system_status: SystemStatus | None = None
        self.chassis_state: ChassisState | None = None
        self.last_target: VisionTarget | None = None
        self.context = MissionContext()
        self._state_lock = threading.RLock()
        self._action_lock = threading.RLock()
        self._safe_stop_manual_confirmed = False
        self._runtime_param_overrides: dict[str, float] = {}
        self._actions = load_robot_actions()
        self._active_patrol_goal = None
        self._active_track_goal = None
        self.callback_groups = build_callback_groups()

        self.mode_pub = self.create_publisher(ModeState, '/robot/mode_state', qos_for('mode_state'))
        self.event_pub = self.create_publisher(EventLog, '/robot/events', qos_for('event_log'))
        self.track_pub = self.create_publisher(Twist, '/robot/track/cmd_vel', qos_for('control_cmd'))
        self.speak_pub = self.create_publisher(SpeakRequest, '/robot/speak_req', qos_for('control_cmd'))
        self.snapshot_pub = self.create_publisher(String, '/robot/vision/snapshot_request', qos_for('control_cmd'))
        self.navigation_route_pub = self.create_publisher(String, '/robot/navigation/route_name', qos_for('control_cmd'))
        self.navigation_goal_id_pub = self.create_publisher(String, '/robot/navigation/goal_id', qos_for('control_cmd'))
        self.navigation_cancel_pub = self.create_publisher(Bool, '/robot/navigation/cancel', qos_for('control_cmd'))
        self.summary_pub = self.create_publisher(String, '/robot/decision/summary', qos_for('status_summary'))
        self.runtime_param_apply_pub = self.create_publisher(String, RUNTIME_PARAM_APPLY_RESULT_TOPIC, qos_for('status_summary'))

        self.mode_guard = ModeGuard(self)
        self.runtime_adapter = RuntimeParamAdapter(self)
        self.mission_orchestrator = MissionOrchestrator(self)
        self.action_runtime = ActionRuntime(self)
        self.side_effects = DecisionSideEffects(node=self)
        self.state_controller = DecisionStateController(node=self)
        self.track_manager = TrackManager(min_confidence=float(self.get_parameter('target_confidence_min').value))
        self.app_service = DecisionAppService(
            node=self,
            ingress=DecisionIngress(),
            policy=DecisionPolicy(node=self),
            state_controller=self.state_controller,
            side_effects=self.side_effects,
            mission_orchestrator=self.mission_orchestrator,
            runtime_adapter=self.runtime_adapter,
            mode_guard=self.mode_guard,
        )

        call_with_callback_group(self.create_subscription, Fault, '/robot/fault', self.on_fault, qos_for('fault_event'), callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_subscription, VoiceCommand, '/robot/voice/cmd', self.on_voice_cmd, qos_for('perception'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, VisionTarget, '/robot/vision/target', self.on_target, qos_for('perception'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/vision/qrcode', self.on_qrcode, qos_for('event_log'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, ChassisState, '/robot/chassis_state', self.on_chassis_state, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, SystemStatus, '/robot/system_status', self.on_system_status, qos_for('telemetry'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/navigation/status', self.on_navigation_status, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, '/robot/runtime/supervision', self.on_runtime_supervision, qos_for('status_summary'), callback_group=self.callback_groups.telemetry)
        call_with_callback_group(self.create_subscription, String, RUNTIME_PARAM_TOPIC, self.on_runtime_params, qos_for('status_summary'), callback_group=self.callback_groups.control)

        call_with_callback_group(self.create_service, SetMode, '/robot/set_mode', self.handle_set_mode, callback_group=self.callback_groups.control)
        call_with_callback_group(self.create_service, ResetFault, '/robot/reset_fault', self.handle_reset_fault, callback_group=self.callback_groups.control)

        boot_delay = float(self.get_parameter('boot_delay_sec').value)
        self.boot_timer = call_with_callback_group(self.create_timer, boot_delay, self.complete_boot, callback_group=self.callback_groups.background)
        self.mode_timer = call_with_callback_group(self.create_timer, 0.20, self.publish_mode, callback_group=self.callback_groups.background)
        self.task_timer = call_with_callback_group(self.create_timer, 0.10, self.tick_tasks, callback_group=self.callback_groups.control)
        self.summary_timer = call_with_callback_group(self.create_timer, 0.50, self.publish_summary, callback_group=self.callback_groups.background)
        self.reducer_timer = call_with_callback_group(self.create_timer, 0.02, self.process_intents, callback_group=self.callback_groups.control)
        self._setup_action_servers()
        self.get_logger().info('robot_decision started in BOOT mode')

    def _mode_guard(self) -> ModeGuard:
        return resolve_mode_guard(self, DecisionNode)

    def _state_controller(self) -> DecisionStateController:
        return resolve_state_controller(self, DecisionNode)

    def _side_effects(self) -> DecisionSideEffects:
        return resolve_side_effects(self, DecisionNode)

    def _runtime_adapter(self) -> RuntimeParamAdapter:
        return resolve_runtime_adapter(self, DecisionNode)

    def _app_service(self) -> DecisionAppService | None:
        return resolve_app_service(self)

    def _normalized_fault_level(self) -> str:
        return DecisionNode._mode_guard(self).normalized_fault_level()

    def _link_ready(self) -> bool:
        return DecisionNode._mode_guard(self).link_ready()

    def _power_ready(self) -> bool:
        return DecisionNode._mode_guard(self).power_ready()

    def _heartbeat_ready(self) -> bool:
        return DecisionNode._mode_guard(self).heartbeat_ready()

    def _manual_recovery_required(self) -> bool:
        return DecisionNode._mode_guard(self).manual_recovery_required()

    def _runtime_param_value(self, key: str, default: float) -> float:
        return DecisionNode._runtime_adapter(self).runtime_param_value(key, default)

    def _estop_active(self) -> bool:
        return DecisionNode._mode_guard(self).estop_active()

    def _safe_stop_recovery_status(self, *, require_manual_confirm: bool = False) -> tuple[bool, str | None]:
        return DecisionNode._mode_guard(self).safe_stop_recovery_status(require_manual_confirm=require_manual_confirm)

    def _command_context(self) -> CommandContext:
        return DecisionNode._mode_guard(self).command_context()

    def _intent_reducer_enabled(self) -> bool:
        service = DecisionNode._app_service(self)
        return bool(service is not None and service.intent_reducer_enabled())

    def _publish_intent_runtime_issue(self, name: str, detail: str, level: str = 'warn') -> None:
        service = DecisionNode._app_service(self)
        if service is not None:
            service.publish_intent_runtime_issue(name, detail, level)
        else:
            DecisionNode._side_effects(self).publish_event('decision_intent', name, detail, level=level)

    def _submit_intent(self, kind: str, payload: object = None) -> bool:
        service = DecisionNode._app_service(self)
        if service is None:
            return False
        return service.submit_intent(kind, payload)

    def _submit_intent_sync(self, kind: str, payload: object = None) -> object:
        service = DecisionNode._app_service(self)
        if service is None:
            raise RuntimeError('decision app service unavailable')
        return service.submit_intent_sync(kind, payload)

    def process_intents(self) -> None:
        service = DecisionNode._app_service(self)
        if service is None:
            return
        service.process_intents()

    def _drain_intent_batch(self, *, max_items: int) -> int:
        service = DecisionNode._app_service(self)
        if service is None:
            return 0
        return service.drain_intent_batch(max_items=max_items)

    @contextmanager
    def state_guard(self) -> Iterator[None]:
        """Hold the serialized decision-state lock."""
        with self._state_lock:
            yield

    def _run_state_mutation(self, description: str, mutation: Callable[[], TState]) -> TState:
        """Execute one state mutation under the serialized decision-state lock.

        Args:
            description: Human-readable description used only for debugging.
            mutation: Callable performing the mutation and returning a value.

        Returns:
            Return value of ``mutation``.

        Raises:
            Any exception raised by ``mutation``.

        Boundary behavior:
            The state lock is always acquired before invoking ``mutation`` so
            callers never observe partially-applied state.
        """
        del description
        with self.state_guard():
            return mutation()

    def complete_boot(self) -> None:
        """Handle the boot-complete timer callback."""
        service = DecisionNode._app_service(self)
        if service is None:
            DecisionNode._state_controller(self).complete_boot_transition()
            return
        service.complete_boot()

    def _mode_state_message(self) -> ModeState:
        """Compatibility wrapper returning the current mode-state message."""
        return DecisionNode._side_effects(self).build_mode_state_message()

    def publish_mode(self) -> None:
        DecisionNode._side_effects(self).publish_mode()

    def publish_summary(self) -> None:
        DecisionNode._side_effects(self).publish_summary()

    def publish_event(self, category: str, name: str, detail: str, level: str = 'info') -> None:
        DecisionNode._side_effects(self).publish_event(category, name, detail, level=level)

    def _system_ready_for_patrol(self) -> bool:
        return DecisionNode._mode_guard(self).system_ready_for_patrol()

    def _emit_snapshot(self, reason: str) -> None:
        DecisionNode._side_effects(self).emit_snapshot(reason)

    def _set_mode_locked(self, new_mode: str, requested_by: str, reason: str) -> None:
        """Apply one mode transition while the state lock is already held.

        Args:
            new_mode: Target logical mode.
            requested_by: Request source label used for audit output.
            reason: Human-readable transition reason.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            This method only updates internal state. Audit events and waiter
            notification are emitted by the application service after the state
            mutation succeeds.
        """
        if new_mode == self.current_mode:
            return
        self.previous_mode = self.current_mode
        self.current_mode = new_mode
        self.context.last_transition_reason = reason
        if new_mode == MODE_SAFE_STOP:
            self._safe_stop_manual_confirmed = False
        elif new_mode != MODE_SAFE_STOP:
            self._safe_stop_manual_confirmed = True
        if new_mode == MODE_PATROL:
            self.context.patrol_started = True
            self.context.patrol_completed = False
            self.context.active_action_name = 'start_patrol'
            self.context.active_action_phase = 'accepted'
            self.context.active_action_message = reason
            self.context.active_action_progress = 0.0
            self.context.navigation_state = 'route_requested'
            self.context.navigation_route_name = str(self.get_parameter('default_patrol_route').value or 'default')
            self.context.navigation_goal_id = ''
            self.context.navigation_goal_label = ''
            self.context.navigation_completed_goals = 0
            self.context.navigation_total_goals = 0
            self.context.navigation_progress = 0.0
            self.context.navigation_reason = reason
            self.context.navigation_cmd_source = 'navigation'
            self.context.navigation_total_goals = 0
        elif new_mode == MODE_TRACK:
            self.context.active_action_name = 'track_target'
            self.context.active_action_phase = 'accepted'
            self.context.active_action_message = reason
            self.context.active_action_progress = 0.0
        else:
            if self.context.active_action_name and new_mode == MODE_IDLE:
                self.context.active_action_phase = 'idle' if self.context.active_action_phase != 'completed' else self.context.active_action_phase
                self.context.active_action_message = reason
                if self.context.active_action_phase != 'completed':
                    self.context.active_action_progress = 0.0
            self.context.active_action_name = '' if new_mode == MODE_IDLE else self.context.active_action_name
        if new_mode != MODE_TRACK:
            self.context.lost_target_count = 0
        if new_mode != MODE_PATROL:
            self.context.navigation_state = 'idle' if new_mode == MODE_IDLE else self.context.navigation_state
            self.context.navigation_goal_id = '' if new_mode != MODE_PATROL else self.context.navigation_goal_id
            self.context.navigation_goal_label = '' if new_mode != MODE_PATROL else self.context.navigation_goal_label
            self.context.navigation_cmd_source = '' if new_mode != MODE_PATROL else self.context.navigation_cmd_source
        del requested_by

    def request_mode_change(self, requested_mode: str, requested_by: str, reason: str) -> tuple[bool, str]:
        """Handle one mode-change request from services, actions, or policy."""
        service = DecisionNode._app_service(self)
        if service is None:
            return DecisionNode._mode_guard(self).request_mode_change(requested_mode, requested_by, reason)
        return service.request_mode_change(requested_mode, requested_by, reason)

    def handle_set_mode(self, request: SetMode.Request, response: SetMode.Response) -> SetMode.Response:
        ok, message = self.request_mode_change(request.mode, request.requested_by, request.reason)
        response.success = ok
        response.message = message
        if hasattr(response, 'trace_id'):
            response.trace_id = str(getattr(request, 'trace_id', '') or '')
        if not ok:
            self.publish_event('mode', 'rejected', message, level='warn')
        return response

    def handle_reset_fault(self, request: ResetFault.Request, response: ResetFault.Response) -> ResetFault.Response:
        service = DecisionNode._app_service(self)
        if service is None:
            ok, message, _ = DecisionNode._state_controller(self).reset_fault_transition(request.requested_by, request.reason)
        else:
            ok, message = service.reset_fault(request.requested_by, request.reason, trace_id=str(getattr(request, 'trace_id', '') or ''))
        response.success = ok
        response.message = message
        if hasattr(response, 'trace_id'):
            response.trace_id = str(getattr(request, 'trace_id', '') or '')
        return response

    def on_fault(self, msg: Fault) -> None:
        service = DecisionNode._app_service(self)
        if service is None:
            DecisionNode._state_controller(self).record_fault(msg)
            return
        service.on_fault(msg)

    def on_voice_cmd(self, msg: VoiceCommand) -> None:
        service = DecisionNode._app_service(self)
        if service is None:
            return
        service.on_voice(msg)

    def on_target(self, msg: VisionTarget) -> None:
        service = DecisionNode._app_service(self)
        if service is None:
            return
        service.on_target(msg)

    def on_qrcode(self, msg: String) -> None:
        service = DecisionNode._app_service(self)
        if service is None:
            return
        service.on_qrcode(msg)

    def on_runtime_params(self, msg: String) -> None:
        service = DecisionNode._app_service(self)
        if service is None:
            outcome = DecisionNode._runtime_adapter(self).apply_message(msg)
            if outcome.ok:
                if hasattr(self, '_run_state_mutation'):
                    DecisionNode._state_controller(self).apply_runtime_overrides(outcome.params)
                else:
                    self._runtime_param_overrides = dict(outcome.params)
                    track_manager = getattr(self, 'track_manager', None)
                    if track_manager is not None:
                        try:
                            track_manager.max_linear = float(outcome.params.get('maxLinearSpeed', track_manager.max_linear))
                            track_manager.max_angular = float(outcome.params.get('maxAngularSpeed', track_manager.max_angular))
                            track_manager.offset_deadband = float(outcome.params.get('trackOffsetDeadband', track_manager.offset_deadband))
                        except Exception:
                            pass
                if hasattr(self, 'notify_state_change'):
                    try:
                        self.notify_state_change()
                    except Exception:
                        pass
            DecisionNode._side_effects(self).publish_runtime_param_apply_result(outcome.apply_result_payload)
            return
        service.on_runtime_params(msg)

    def on_chassis_state(self, msg: ChassisState) -> None:
        service = DecisionNode._app_service(self)
        if service is None:
            DecisionNode._state_controller(self).cache_chassis_state(msg)
            return
        service.on_chassis_state(msg)

    def on_system_status(self, msg: SystemStatus) -> None:
        service = DecisionNode._app_service(self)
        if service is None:
            DecisionNode._state_controller(self).cache_system_status(msg)
            return
        service.on_system_status(msg)

    def on_navigation_status(self, msg: String) -> None:
        """Forward one navigation lifecycle update into the decision app service.

        Args:
            msg: Navigation status JSON payload emitted by ``robot_navigation``.

        Returns:
            None.

        Raises:
            None. Malformed payloads are handled inside the ingress/app-service layer.
        """
        service = DecisionNode._app_service(self)
        if service is None:
            return
        service.on_navigation_status(msg)

    def on_runtime_supervision(self, msg: String) -> None:
        """Forward one runtime-supervision report into the decision app service."""
        service = DecisionNode._app_service(self)
        if service is None:
            return
        service.on_runtime_supervision(msg)

    def tick_tasks(self) -> None:
        service = DecisionNode._app_service(self)
        if service is None:
            return
        service.tick_tasks()

    def _setup_action_servers(self) -> None:
        if not self._actions or ActionServer is None or GoalResponse is None or CancelResponse is None:
            self.get_logger().info('ROS action support unavailable; long-task services remain in compatibility mode')
            self.start_patrol_action_server = None
            self.track_target_action_server = None
            return
        self.start_patrol_action_server = call_with_callback_group(
            ActionServer,
            self,
            self._actions['StartPatrol'],
            '/robot/actions/start_patrol',
            execute_callback=self.execute_start_patrol,
            goal_callback=self.on_start_patrol_goal,
            cancel_callback=self.on_action_cancel,
            callback_group=self.callback_groups.control,
        )
        self.track_target_action_server = call_with_callback_group(
            ActionServer,
            self,
            self._actions['TrackTarget'],
            '/robot/actions/track_target',
            execute_callback=self.execute_track_target,
            goal_callback=self.on_track_target_goal,
            cancel_callback=self.on_action_cancel,
            callback_group=self.callback_groups.control,
        )

    def on_start_patrol_goal(self, goal_request: object):
        del goal_request
        with self.state_guard():
            if GoalResponse is None:
                return self.current_mode in {MODE_IDLE, MODE_PATROL}
            if self.current_mode not in {MODE_IDLE, MODE_PATROL}:
                return GoalResponse.REJECT
            return GoalResponse.ACCEPT

    def on_track_target_goal(self, goal_request: object):
        del goal_request
        with self.state_guard():
            if GoalResponse is None:
                return self.current_mode in {MODE_IDLE, MODE_TRACK, 'MANUAL'}
            if self.current_mode not in {MODE_IDLE, MODE_TRACK, 'MANUAL'}:
                return GoalResponse.REJECT
            return GoalResponse.ACCEPT

    def on_action_cancel(self, goal_handle: object):
        del goal_handle
        self.notify_state_change()
        if CancelResponse is None:
            return True
        return CancelResponse.ACCEPT

    def execute_start_patrol(self, goal_handle: object):
        return self.action_runtime.execute_start_patrol(goal_handle)

    def execute_track_target(self, goal_handle: object):
        return self.action_runtime.execute_track_target(goal_handle)

    def notify_state_change(self) -> None:
        """Notify action waiters after any state mutation."""
        DecisionNode._side_effects(self).notify_state_change()

    def destroy_node(self):
        """Release reducer/action runtime resources before delegating to ROS teardown.

        Args:
            None.

        Returns:
            Underlying ``Node.destroy_node`` return value when available, else
            ``True``.

        Raises:
            None.
        """
        service = DecisionNode._app_service(self)
        if service is not None and service.intent_reducer_enabled():
            service.shutdown()
            try:
                service.drain_intent_batch(max_items=getattr(service, '_intent_batch_max', 32))
            except Exception:
                pass
        reducer_timer = getattr(self, 'reducer_timer', None)
        if reducer_timer is not None:
            try:
                reducer_timer.cancel()
            except Exception:
                pass
        if getattr(self, 'action_runtime', None) is not None:
            self.action_runtime.notify_shutdown()
        destroy = getattr(Node, 'destroy_node', None)
        if destroy is None:
            return True
        try:
            return destroy(self)
        except Exception:
            return True


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = DecisionNode()
    if MultiThreadedExecutor is None:
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()
            rclpy.shutdown()
        return
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
