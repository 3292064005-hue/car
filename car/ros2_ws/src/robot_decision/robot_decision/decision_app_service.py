from __future__ import annotations

"""Application service for decision-layer intent handling."""

from typing import Any

from robot_decision.decision_ingress import (
    DecisionIngress,
    NavigationStatusIntent,
    QrcodeIntent,
    RequestModeChangeIntent,
    ResetFaultIntent,
    RuntimeOrchestrationIntent,
    RuntimeParamsIntent,
    RuntimeSupervisionIntent,
)
from robot_decision.decision_policy import DecisionPolicy
from robot_decision.decision_side_effects import DecisionSideEffects
from robot_decision.decision_state_controller import DecisionStateController
from robot_decision.intent_reducer import DecisionIntentReducer
from robot_decision.mission_orchestrator import MissionOrchestrator, MissionTickPlan
from robot_decision.mode_guard import ModeGuard
from robot_decision.runtime_param_adapter import RuntimeParamAdapter
from robot_decision.runtime_orchestration_controller import RuntimeOrchestrationController
from robot_utils.constants import MODE_BOOT, MODE_PATROL, MODE_SAFE_STOP


class DecisionAppService:
    """Coordinate ingress, policy, state mutation, and side effects."""

    def __init__(
        self,
        *,
        node: Any,
        ingress: DecisionIngress,
        policy: DecisionPolicy,
        state_controller: DecisionStateController,
        side_effects: DecisionSideEffects,
        mission_orchestrator: MissionOrchestrator,
        runtime_adapter: RuntimeParamAdapter,
        mode_guard: ModeGuard,
    ) -> None:
        self._node = node
        self._ingress = ingress
        self._policy = policy
        self._state_controller = state_controller
        self._side_effects = side_effects
        self._mission_orchestrator = mission_orchestrator
        self._runtime_adapter = runtime_adapter
        self._mode_guard = mode_guard
        self._intent_queue_max = int(self._node.get_parameter('decision_intent_queue_max').value)
        self._intent_batch_max = int(self._node.get_parameter('decision_intent_batch_max').value)
        self._intent_sync_timeout_sec = float(self._node.get_parameter('decision_intent_sync_timeout_sec').value)
        self._intent_reducer_shutdown = False
        self.intent_reducer = DecisionIntentReducer(
            queue_max=self._intent_queue_max,
            batch_max=self._intent_batch_max,
            sync_timeout_sec=self._intent_sync_timeout_sec,
            resolve_intent=self.dispatch_intent,
            publish_issue=self.publish_intent_runtime_issue,
        )

    def intent_reducer_enabled(self) -> bool:
        return bool(self.intent_reducer.enabled) and not self._intent_reducer_shutdown

    def submit_intent(self, kind: str, payload: object = None) -> bool:
        return self.intent_reducer.submit_async(kind, payload)

    def submit_intent_sync(self, kind: str, payload: object = None) -> object:
        return self.intent_reducer.submit_sync(kind, payload)

    def process_intents(self) -> None:
        self.intent_reducer.process()

    def drain_intent_batch(self, *, max_items: int | None = None) -> int:
        return self.intent_reducer.drain_batch(max_items=max_items or self._intent_batch_max)

    def shutdown(self) -> None:
        self._intent_reducer_shutdown = True
        self.intent_reducer.shutdown()

    def publish_intent_runtime_issue(self, name: str, detail: str, level: str = 'warn') -> None:
        self._side_effects.publish_event('decision_intent', name, detail, level=level)

    def dispatch_intent(self, kind: str, payload: object = None) -> object:
        if kind == 'complete_boot':
            return self._complete_boot_now()
        if kind == 'request_mode_change':
            if not isinstance(payload, dict):
                raise TypeError('request_mode_change payload must be a dict')
            intent = RequestModeChangeIntent(
                requested_mode=str(payload.get('requested_mode', '') or ''),
                requested_by=str(payload.get('requested_by', '') or ''),
                reason=str(payload.get('reason', '') or ''),
                trace_id=str(payload.get('trace_id', '') or ''),
            )
            return self._request_mode_change_now(intent)
        if kind == 'reset_fault':
            if not isinstance(payload, dict):
                raise TypeError('reset_fault payload must be a dict')
            intent = ResetFaultIntent(
                requested_by=str(payload.get('requested_by', '') or ''),
                reason=str(payload.get('reason', '') or ''),
                trace_id=str(payload.get('trace_id', '') or ''),
            )
            return self._reset_fault_now(intent)
        if kind == 'fault':
            self._handle_fault_now(payload)
            return None
        if kind == 'voice_cmd':
            self._handle_voice_now(payload)
            return None
        if kind == 'target':
            self._handle_target_now(payload)
            return None
        if kind == 'qrcode':
            self._handle_qrcode_now(payload)
            return None
        if kind == 'runtime_params':
            self._handle_runtime_params_now(payload)
            return None
        if kind == 'navigation_status':
            self._handle_navigation_status_now(payload)
            return None
        if kind == 'runtime_supervision':
            self._handle_runtime_supervision_now(payload)
            return None
        if kind == 'runtime_orchestration':
            self._handle_runtime_orchestration_now(payload)
            return None
        if kind == 'chassis_state':
            self._handle_chassis_state_now(payload)
            return None
        if kind == 'system_status':
            self._handle_system_status_now(payload)
            return None
        if kind == 'tick_tasks':
            self._handle_tick_tasks_now()
            return None
        raise ValueError(f'unknown decision intent kind: {kind}')

    def complete_boot(self) -> None:
        if self.intent_reducer_enabled():
            try:
                self.submit_intent_sync('complete_boot')
                return
            except Exception as exc:
                self.publish_intent_runtime_issue('intent_error', f'complete_boot:{exc}', level='error')
        self._complete_boot_now()

    def request_mode_change(self, requested_mode: str, requested_by: str, reason: str, *, trace_id: str = '') -> tuple[bool, str]:
        intent = RequestModeChangeIntent(requested_mode=requested_mode, requested_by=requested_by, reason=reason, trace_id=trace_id)
        if self.intent_reducer_enabled():
            try:
                return self.submit_intent_sync(
                    'request_mode_change',
                    {
                        'requested_mode': intent.requested_mode,
                        'requested_by': intent.requested_by,
                        'reason': intent.reason,
                        'trace_id': intent.trace_id,
                    },
                )
            except (RuntimeError, TimeoutError) as exc:
                self.publish_intent_runtime_issue('intent_rejected', f'request_mode_change:{exc}')
                return False, 'decision_busy'
        return self._request_mode_change_now(intent)

    def reset_fault(self, requested_by: str, reason: str, *, trace_id: str = '') -> tuple[bool, str]:
        intent = ResetFaultIntent(requested_by=requested_by, reason=reason, trace_id=trace_id)
        if self.intent_reducer_enabled():
            try:
                return self.submit_intent_sync(
                    'reset_fault',
                    {'requested_by': intent.requested_by, 'reason': intent.reason, 'trace_id': intent.trace_id},
                )
            except (RuntimeError, TimeoutError) as exc:
                self.publish_intent_runtime_issue('intent_rejected', f'reset_fault:{exc}')
                return False, 'decision_busy'
        return self._reset_fault_now(intent)

    def on_fault(self, msg: Any) -> None:
        parsed = self._ingress.parse_fault_msg(msg)
        if self.intent_reducer_enabled():
            try:
                self.submit_intent_sync('fault', parsed)
                return
            except (RuntimeError, TimeoutError) as exc:
                self.publish_intent_runtime_issue('intent_rejected', f'fault:{exc}', level='error')
        self._handle_fault_now(parsed)

    def on_voice(self, msg: Any) -> None:
        parsed = self._ingress.parse_voice_msg(msg)
        if self.intent_reducer_enabled() and self.submit_intent('voice_cmd', parsed):
            return
        self._handle_voice_now(parsed)

    def on_target(self, msg: Any) -> None:
        parsed = self._ingress.parse_target_msg(msg)
        if self.intent_reducer_enabled() and self.submit_intent('target', parsed):
            return
        self._handle_target_now(parsed)

    def on_qrcode(self, msg: Any) -> None:
        intent = self._ingress.parse_qrcode_msg(msg)
        if not intent.data:
            return
        if self.intent_reducer_enabled() and self.submit_intent('qrcode', intent):
            return
        self._handle_qrcode_now(intent)

    def on_runtime_params(self, msg: Any) -> None:
        try:
            intent = self._ingress.parse_runtime_params_msg(msg)
        except Exception:
            outcome = self._runtime_adapter.apply_message(msg)
            if outcome.ok:
                self._state_controller.apply_runtime_overrides(outcome.params)
                self._side_effects.notify_state_change()
            self._side_effects.publish_runtime_param_apply_result(outcome.apply_result_payload)
            return
        if self.intent_reducer_enabled():
            try:
                self.submit_intent_sync('runtime_params', intent)
                return
            except (RuntimeError, TimeoutError) as exc:
                self.publish_intent_runtime_issue('intent_rejected', f'runtime_params:{exc}')
        self._handle_runtime_params_now(intent)

    def on_navigation_status(self, msg: Any) -> None:
        intent = self._ingress.parse_navigation_status_msg(msg)
        if self.intent_reducer_enabled() and self.submit_intent('navigation_status', intent):
            return
        self._handle_navigation_status_now(intent)

    def on_runtime_supervision(self, msg: Any) -> None:
        intent = self._ingress.parse_runtime_supervision_msg(msg)
        if self.intent_reducer_enabled() and self.submit_intent('runtime_supervision', intent):
            return
        self._handle_runtime_supervision_now(intent)

    def on_runtime_orchestration(self, msg: Any) -> None:
        intent = self._ingress.parse_runtime_orchestration_msg(msg)
        if self.intent_reducer_enabled() and self.submit_intent('runtime_orchestration', intent):
            return
        self._handle_runtime_orchestration_now(intent)

    def on_chassis_state(self, msg: Any) -> None:
        parsed = self._ingress.parse_chassis_state_msg(msg)
        if self.intent_reducer_enabled() and self.submit_intent('chassis_state', parsed):
            return
        self._handle_chassis_state_now(parsed)

    def on_system_status(self, msg: Any) -> None:
        parsed = self._ingress.parse_system_status_msg(msg)
        if self.intent_reducer_enabled():
            try:
                self.submit_intent_sync('system_status', parsed)
                return
            except (RuntimeError, TimeoutError) as exc:
                self.publish_intent_runtime_issue('intent_rejected', f'system_status:{exc}', level='error')
        self._handle_system_status_now(parsed)

    def tick_tasks(self) -> None:
        if self.intent_reducer_enabled() and self.submit_intent('tick_tasks'):
            return
        self._handle_tick_tasks_now()

    def _complete_boot_now(self) -> None:
        transition, effects = self._policy.build_boot_effects(current_mode=self._node.current_mode)
        changed = self._state_controller.complete_boot_transition()
        self._side_effects.emit_effect_plan(effects)
        if transition is not None and changed:
            self._side_effects.publish_mode_transition_event(requested_by=transition.requested_by, reason=transition.reason)
            self._emit_mode_transition_side_effects(previous_mode='BOOT', new_mode=self._node.current_mode)
            self._side_effects.notify_state_change()

    def _request_mode_change_now(self, intent: RequestModeChangeIntent) -> tuple[bool, str]:
        previous_mode = self._node.current_mode
        ok, message = self._mode_guard.request_mode_change(intent.requested_mode, intent.requested_by, intent.reason)
        if ok and self._node.current_mode != previous_mode:
            self._side_effects.publish_mode_transition_event(requested_by=intent.requested_by, reason=intent.reason)
            self._emit_mode_transition_side_effects(previous_mode=previous_mode, new_mode=self._node.current_mode)
            self._side_effects.notify_state_change()
        return ok, message

    def _reset_fault_now(self, intent: ResetFaultIntent) -> tuple[bool, str]:
        previous_mode = self._node.current_mode
        ok, message, changed = self._state_controller.reset_fault_transition(intent.requested_by, intent.reason)
        if ok and changed and self._node.current_mode != previous_mode:
            self._side_effects.publish_mode_transition_event(requested_by=intent.requested_by, reason=intent.reason or 'fault_reset')
            self._emit_mode_transition_side_effects(previous_mode=previous_mode, new_mode=self._node.current_mode)
            self._side_effects.notify_state_change()
        return ok, message

    def _handle_fault_now(self, msg: Any) -> None:
        decision = self._policy.evaluate_fault(msg)
        self._state_controller.record_fault(msg)
        mode_changed = False
        previous_mode = self._node.current_mode
        if decision.transition is not None:
            mode_changed = self._state_controller.apply_mode_transition(
                decision.transition.new_mode,
                decision.transition.requested_by,
                decision.transition.reason,
            )
        self._side_effects.emit_effect_plan(decision.effect_plan)
        if mode_changed:
            self._side_effects.publish_mode_transition_event(
                requested_by=decision.transition.requested_by,
                reason=decision.transition.reason,
            )
            self._emit_mode_transition_side_effects(previous_mode=previous_mode, new_mode=self._node.current_mode)
        self._side_effects.notify_state_change()

    def _handle_voice_now(self, msg: Any) -> None:
        self._state_controller.record_voice_command(str(getattr(msg, 'command', '') or ''))
        decision = self._policy.evaluate_voice_command(msg)
        self._side_effects.emit_effect_plan(decision.effect_plan)
        if decision.should_reset_fault:
            self._reset_fault_now(ResetFaultIntent(requested_by='voice', reason='voice_reset_fault'))
            return
        if decision.transition is not None:
            self._request_mode_change_now(
                RequestModeChangeIntent(
                    requested_mode=decision.transition.new_mode,
                    requested_by=decision.transition.requested_by,
                    reason=decision.transition.reason,
                )
            )
            return
        if decision.accepted:
            self._side_effects.notify_state_change()

    def _handle_target_now(self, msg: Any) -> None:
        track_cmd = self._state_controller.record_target(msg)
        decision = self._policy.evaluate_target(msg)
        if track_cmd is not None:
            self._side_effects.publish_track_cmd(track_cmd)
        if decision.transition is not None:
            previous_mode = self._node.current_mode
            changed = self._state_controller.apply_mode_transition(
                decision.transition.new_mode,
                decision.transition.requested_by,
                decision.transition.reason,
            )
            if changed and self._node.current_mode != previous_mode:
                self._side_effects.publish_mode_transition_event(
                    requested_by=decision.transition.requested_by,
                    reason=decision.transition.reason,
                )
                self._emit_mode_transition_side_effects(previous_mode=previous_mode, new_mode=self._node.current_mode)
        self._side_effects.emit_effect_plan(decision.effect_plan)
        self._side_effects.notify_state_change()

    def _handle_qrcode_now(self, payload: QrcodeIntent | Any) -> None:
        intent = payload if isinstance(payload, QrcodeIntent) else self._ingress.parse_qrcode_msg(payload)
        if not intent.data:
            return
        self._state_controller.record_qrcode(intent.data)
        decision = self._policy.evaluate_qrcode(intent.data)
        self._side_effects.emit_effect_plan(decision.effect_plan)
        self._side_effects.notify_state_change()

    def _handle_runtime_params_now(self, payload: RuntimeParamsIntent | Any) -> None:
        intent = payload if isinstance(payload, RuntimeParamsIntent) else self._ingress.parse_runtime_params_msg(payload)
        outcome = self._runtime_adapter.apply_payload(intent.payload)
        if outcome.ok:
            self._state_controller.apply_runtime_overrides(outcome.params)
            self._side_effects.notify_state_change()
        self._side_effects.publish_runtime_param_apply_result(outcome.apply_result_payload)

    def _handle_navigation_status_now(self, payload: NavigationStatusIntent | Any) -> None:
        intent = payload if isinstance(payload, NavigationStatusIntent) else self._ingress.parse_navigation_status_msg(payload)
        self._state_controller.cache_navigation_status(intent.payload)
        self._side_effects.notify_state_change()

    def _handle_runtime_supervision_now(self, payload: RuntimeSupervisionIntent | Any) -> None:
        intent = payload if isinstance(payload, RuntimeSupervisionIntent) else self._ingress.parse_runtime_supervision_msg(payload)
        orchestration = getattr(self._node, 'runtime_orchestration', None)
        if orchestration is None:
            orchestration = RuntimeOrchestrationController(self._node)
        orchestration_decision = orchestration.evaluate(intent.payload)
        self._state_controller.cache_runtime_supervision(intent.payload, orchestration_decision=orchestration_decision)
        state = str(intent.payload.get('state', '') or '')
        reasons = intent.payload.get('reasons', [])
        primary_reason = str(reasons[0] if isinstance(reasons, list) and reasons else state or 'runtime_supervision')
        if orchestration_decision.orchestration_state in {'degraded', 'recovering', 'blocked'}:
            self._side_effects.publish_event('runtime_orchestration', orchestration_decision.operator_event_name, orchestration_decision.operator_event_detail, level='warn' if orchestration_decision.orchestration_state in {'recovering', 'blocked'} else 'info')
        should_force_safe_stop = state in {'faulted', 'unavailable'} and self._node.current_mode not in {MODE_BOOT, MODE_SAFE_STOP}
        transition_reason = primary_reason
        if orchestration_decision.should_force_safe_stop:
            should_force_safe_stop = True
            transition_reason = orchestration_decision.transition_reason or primary_reason
        if should_force_safe_stop:
            previous_mode = self._node.current_mode
            changed = self._state_controller.apply_mode_transition(MODE_SAFE_STOP, 'runtime_supervisor', transition_reason)
            if changed:
                self._side_effects.publish_mode_transition_event(requested_by='runtime_supervisor', reason=transition_reason)
                self._side_effects.publish_event('runtime_supervision', state or 'runtime_orchestration', transition_reason, level='warn')
                self._emit_mode_transition_side_effects(previous_mode=previous_mode, new_mode=self._node.current_mode)
        self._side_effects.notify_state_change()

    def _handle_runtime_orchestration_now(self, payload: RuntimeOrchestrationIntent | Any) -> None:
        intent = payload if isinstance(payload, RuntimeOrchestrationIntent) else self._ingress.parse_runtime_orchestration_msg(payload)
        orchestration_payload = intent.payload
        self._state_controller.cache_runtime_orchestration(orchestration_payload)
        orchestration_state = str(orchestration_payload.get('state', '') or '')
        orchestration_reason = str(orchestration_payload.get('reason', '') or '')
        if orchestration_state in {'degraded', 'recovering', 'shutting_down'}:
            self._side_effects.publish_event('runtime_orchestration', orchestration_state, orchestration_reason or orchestration_state, level='warn' if orchestration_state != 'degraded' else 'info')
        if orchestration_state in {'recovering', 'shutting_down'} and self._node.current_mode not in {MODE_BOOT, MODE_SAFE_STOP}:
            previous_mode = self._node.current_mode
            changed = self._state_controller.apply_mode_transition(MODE_SAFE_STOP, 'runtime_orchestration_manager', orchestration_reason or orchestration_state)
            if changed:
                self._side_effects.publish_mode_transition_event(requested_by='runtime_orchestration_manager', reason=orchestration_reason or orchestration_state)
                self._side_effects.publish_event('runtime_orchestration', orchestration_state, orchestration_reason or orchestration_state, level='warn')
                self._emit_mode_transition_side_effects(previous_mode=previous_mode, new_mode=self._node.current_mode)
        self._side_effects.notify_state_change()

    def _handle_chassis_state_now(self, msg: Any) -> None:
        self._state_controller.cache_chassis_state(msg)
        self._side_effects.notify_state_change()

    def _handle_system_status_now(self, msg: Any) -> None:
        previous_status = self._state_controller.cache_system_status(msg)
        decision = self._policy.evaluate_system_status(msg, previous_status)
        self._side_effects.emit_effect_plan(decision.effect_plan)
        if decision.transition is not None:
            previous_mode = self._node.current_mode
            changed = self._state_controller.apply_mode_transition(
                decision.transition.new_mode,
                decision.transition.requested_by,
                decision.transition.reason,
            )
            if changed:
                self._side_effects.publish_mode_transition_event(
                    requested_by=decision.transition.requested_by,
                    reason=decision.transition.reason,
                )
                self._emit_mode_transition_side_effects(previous_mode=previous_mode, new_mode=self._node.current_mode)
        self._side_effects.notify_state_change()

    def _handle_tick_tasks_now(self) -> None:
        plan: MissionTickPlan = self._mission_orchestrator.tick_tasks()
        if plan.track_cmd is not None:
            self._side_effects.publish_track_cmd(plan.track_cmd)
        if plan.navigation_route_name:
            self._side_effects.publish_navigation_route(plan.navigation_route_name)
            self._side_effects.publish_event('mission', 'stage_advance', f'route={plan.navigation_route_name}', level='info')
        self._side_effects.emit_effect_plan(plan.effect_plan)
        if plan.transition is not None:
            previous_mode = self._node.current_mode
            changed = self._state_controller.apply_mode_transition(
                plan.transition.new_mode,
                plan.transition.requested_by,
                plan.transition.reason,
            )
            if changed:
                self._side_effects.publish_mode_transition_event(
                    requested_by=plan.transition.requested_by,
                    reason=plan.transition.reason,
                )
                self._emit_mode_transition_side_effects(previous_mode=previous_mode, new_mode=self._node.current_mode)
        if plan.notify_state_change:
            self._side_effects.notify_state_change()

    def _emit_mode_transition_side_effects(self, *, previous_mode: str, new_mode: str) -> None:
        """Emit auxiliary mission side effects required by mode transitions.

        Args:
            previous_mode: Mode before the transition.
            new_mode: Mode after the transition.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            Entering patrol delegates motion generation to navigation by sending
            the configured default route. Leaving patrol always sends a cancel so
            abandoned navigation missions cannot keep commanding motion.
        """
        if previous_mode == MODE_PATROL and new_mode != MODE_PATROL:
            self._side_effects.publish_navigation_cancel(reason=f'patrol_exit:{new_mode}')
        if previous_mode != MODE_PATROL and new_mode == MODE_PATROL:
            active_mission = getattr(self._node, 'active_mission_entry', None)
            route_name = ''
            if active_mission is not None:
                route_name = str(getattr(active_mission, 'route_name', '') or '')
            if not route_name:
                route_name = str(getattr(self._node.context, 'planned_route_name', '') or '')
            if not route_name:
                route_name = str(self._node.get_parameter('default_patrol_route').value or 'default')
            self._side_effects.publish_navigation_route(route_name)
            mission_id = str(getattr(self._node.context, 'active_mission_id', '') or '')
            task_profile = str(getattr(self._node.context, 'active_task_profile', '') or '')
            detail = f'patrol delegated to navigation route={route_name}'
            if mission_id:
                detail += f' mission={mission_id}'
            if task_profile:
                detail += f' taskProfile={task_profile}'
            self._side_effects.publish_event('navigation', 'route_start', detail, level='info')
