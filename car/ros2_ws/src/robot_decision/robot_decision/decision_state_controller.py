from __future__ import annotations

"""State-transition controller for the decision runtime."""

from typing import Any

from geometry_msgs.msg import Twist

from robot_utils.constants import MODE_FAULT, MODE_IDLE, MODE_PATROL, MODE_TRACK


class DecisionStateController:
    """Own serialized state mutation for decision intents.

    The controller is intentionally side-effect free: it only mutates internal
    decision-layer state under the node lock. ROS-visible publishing is handled
    by ``DecisionSideEffects``.
    """

    def __init__(self, *, node: Any) -> None:
        self._node = node

    def resolve_intent(self, kind: str, payload: object = None) -> object:
        app_service = getattr(self._node, 'app_service', None)
        dispatch_intent = getattr(app_service, 'dispatch_intent', None)
        if callable(dispatch_intent):
            return dispatch_intent(kind, payload)
        if kind == 'complete_boot':
            return self.complete_boot_transition()
        if kind == 'reset_fault':
            if not isinstance(payload, dict):
                raise TypeError('reset_fault payload must be a dict')
            return self.reset_fault_transition(str(payload.get('requested_by', '')), str(payload.get('reason', '')))
        if kind == 'fault':
            self.record_fault(payload)
            return None
        if kind == 'voice_cmd':
            self.record_voice_command(str(getattr(payload, 'command', '') or ''))
            return None
        if kind == 'target':
            return self.record_target(payload)
        if kind == 'qrcode':
            if isinstance(payload, str):
                self.record_qrcode(payload)
                return None
            self.record_qrcode(str(getattr(payload, 'data', '') or ''))
            return None
        if kind == 'runtime_params':
            if not isinstance(payload, dict):
                raise TypeError('runtime_params payload must be a dict')
            self.apply_runtime_overrides(payload)
            return None
        if kind == 'navigation_status':
            if not isinstance(payload, dict):
                raise TypeError('navigation_status payload must be a dict')
            self.cache_navigation_status(payload)
            return None
        if kind == 'runtime_supervision':
            if not isinstance(payload, dict):
                raise TypeError('runtime_supervision payload must be a dict')
            self.cache_runtime_supervision(payload)
            return None
        if kind == 'chassis_state':
            self.cache_chassis_state(payload)
            return None
        if kind == 'system_status':
            return self.cache_system_status(payload)
        raise ValueError(f'unknown decision intent kind: {kind}')

    def complete_boot_transition(self) -> bool:
        transitioned = False

        def _mutation() -> None:
            nonlocal transitioned
            if self._node.current_mode == 'BOOT':
                transitioned = self.apply_mode_transition_locked(MODE_IDLE, 'system', 'boot_complete')
            timer = getattr(self._node, 'boot_timer', None)
            if timer is not None:
                try:
                    timer.cancel()
                except Exception:
                    pass

        self._node._run_state_mutation('complete_boot', _mutation)
        return transitioned

    def apply_mode_transition(self, new_mode: str, requested_by: str, reason: str) -> bool:
        changed = False

        def _mutation() -> None:
            nonlocal changed
            changed = self.apply_mode_transition_locked(new_mode, requested_by, reason)

        self._node._run_state_mutation('set_mode', _mutation)
        return changed

    def apply_mode_transition_locked(self, new_mode: str, requested_by: str, reason: str) -> bool:
        previous_mode = self._node.current_mode
        self._node._set_mode_locked(new_mode, requested_by, reason)
        return previous_mode != self._node.current_mode

    def reset_fault_transition(self, requested_by: str, reason: str) -> tuple[bool, str, bool]:
        result = {'success': False, 'message': 'fault reset failed', 'mode_changed': False}

        def _mutation() -> None:
            if self._node.current_mode != MODE_FAULT:
                result['success'] = True
                result['message'] = 'system not in FAULT mode'
                return
            self._node.last_fault = None
            self._node._safe_stop_manual_confirmed = True
            result['mode_changed'] = self.apply_mode_transition_locked(MODE_IDLE, requested_by, reason or 'fault_reset')
            result['success'] = True
            result['message'] = 'fault reset complete'

        self._node._run_state_mutation('handle_reset_fault', _mutation)
        return bool(result['success']), str(result['message']), bool(result['mode_changed'])

    def record_fault(self, msg: Any) -> None:
        def _mutation() -> None:
            self._node.last_fault = msg
            entry = f"{getattr(msg, 'code', '')}:{getattr(msg, 'level', '')}"
            self._node.context.fault_history.append(entry)
            if len(self._node.context.fault_history) > 10:
                self._node.context.fault_history = self._node.context.fault_history[-10:]

        self._node._run_state_mutation('record_fault', _mutation)

    def record_voice_command(self, command: str) -> None:
        self._node._run_state_mutation('record_voice_command', lambda: setattr(self._node.context, 'last_voice_command', str(command or '')))

    def record_target(self, msg: Any) -> Twist | None:
        track_cmd: Twist | None = None

        def _mutation() -> None:
            nonlocal track_cmd
            self._node.last_target = msg
            self._node.context.track_target_valid = bool(getattr(msg, 'detected', False))
            self._node.context.last_target_type = str(getattr(msg, 'target_type', '') or '')
            if self._node.current_mode == MODE_PATROL and bool(getattr(msg, 'detected', False)):
                self._node.context.last_target_type = str(getattr(msg, 'target_type', '') or '')
            if self._node.current_mode == MODE_TRACK:
                track_cmd = self._node.track_manager.compute_cmd(msg)
                min_conf = float(self._node.get_parameter('target_confidence_min').value)
                if bool(getattr(msg, 'detected', False)) and float(getattr(msg, 'confidence', 0.0) or 0.0) >= min_conf:
                    self._node.context.lost_target_count = 0
                else:
                    self._node.context.lost_target_count += 1

        self._node._run_state_mutation('record_target', _mutation)
        return track_cmd

    def record_qrcode(self, data: str) -> None:
        self._node._run_state_mutation('record_qrcode', lambda: setattr(self._node.context, 'last_qrcode', str(data or '')))

    def apply_runtime_overrides(self, params: dict[str, Any]) -> None:
        def _mutation() -> None:
            self._node._runtime_param_overrides = dict(params)
            self._node.track_manager.max_linear = self._coerce_float(params.get('maxLinearSpeed'), self._node.track_manager.max_linear)
            self._node.track_manager.max_angular = self._coerce_float(params.get('maxAngularSpeed'), self._node.track_manager.max_angular)
            self._node.track_manager.offset_deadband = self._coerce_float(params.get('trackOffsetDeadband'), self._node.track_manager.offset_deadband)

        self._node._run_state_mutation('apply_runtime_overrides', _mutation)

    def cache_navigation_status(self, payload: dict[str, Any]) -> None:
        """Cache the latest navigation lifecycle projection for patrol orchestration."""

        def _mutation() -> None:
            context = self._node.context
            context.navigation_state = str(payload.get('state', context.navigation_state) or context.navigation_state)
            context.navigation_route_name = str(payload.get('routeName', context.navigation_route_name) or '')
            context.navigation_goal_id = str(payload.get('goalId', context.navigation_goal_id) or '')
            context.navigation_goal_label = str(payload.get('goalLabel', context.navigation_goal_label) or '')
            context.navigation_completed_goals = int(payload.get('completedGoals', context.navigation_completed_goals) or 0)
            context.navigation_total_goals = int(payload.get('totalGoals', context.navigation_total_goals) or 0)
            try:
                context.navigation_progress = float(payload.get('progress', context.navigation_progress) or 0.0)
            except (TypeError, ValueError):
                context.navigation_progress = float(context.navigation_progress)
            context.navigation_reason = str(payload.get('reason', context.navigation_reason) or '')
            context.navigation_cmd_source = str(payload.get('cmdSource', context.navigation_cmd_source) or '')
            context.navigation_last_update_at = str(payload.get('updatedAt', context.navigation_last_update_at) or '')
            context.current_step_name = context.navigation_goal_label or context.navigation_goal_id
            context.patrol_index = context.navigation_completed_goals
            if context.navigation_total_goals > 0 and context.navigation_state == 'route_completed':
                context.patrol_completed = True
                context.active_action_progress = 1.0
                context.active_action_phase = 'completed'
                context.active_action_message = 'patrol_complete'
            elif self._node.current_mode == MODE_PATROL:
                context.patrol_started = True
                context.patrol_completed = False
                context.active_action_name = 'start_patrol'
                context.active_action_phase = 'running' if context.navigation_state not in {'failed', 'cancelled'} else 'aborted'
                context.active_action_progress = float(context.navigation_progress)
                context.active_action_message = context.navigation_reason or context.navigation_goal_label or context.navigation_state

        self._node._run_state_mutation('navigation_status', _mutation)

    def cache_runtime_supervision(self, payload: dict[str, Any]) -> None:
        """Cache runtime supervision state for audit and operator feedback."""

        def _mutation() -> None:
            context = self._node.context
            context.runtime_supervision_state = str(payload.get('state', context.runtime_supervision_state) or context.runtime_supervision_state)
            reasons = payload.get('reasons', context.runtime_supervision_reasons)
            context.runtime_supervision_reasons = [str(item) for item in reasons] if isinstance(reasons, list) else list(context.runtime_supervision_reasons)
            components = payload.get('components', context.runtime_supervision_components)
            context.runtime_supervision_components = dict(components) if isinstance(components, dict) else dict(context.runtime_supervision_components)

        self._node._run_state_mutation('runtime_supervision', _mutation)

    def cache_chassis_state(self, msg: Any) -> None:
        self._node._run_state_mutation('on_chassis_state', lambda: setattr(self._node, 'chassis_state', msg))

    def cache_system_status(self, msg: Any) -> Any | None:
        previous_status = {'value': None}

        def _mutation() -> None:
            previous_status['value'] = self._node.system_status
            self._node.system_status = msg

        self._node._run_state_mutation('on_system_status', _mutation)
        return previous_status['value']

    def _coerce_float(self, value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)
