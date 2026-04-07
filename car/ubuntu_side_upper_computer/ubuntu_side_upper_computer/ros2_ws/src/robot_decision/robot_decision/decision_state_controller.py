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
        """Compatibility wrapper that dispatches one legacy intent kind.

        Args:
            kind: Legacy intent identifier.
            payload: Legacy payload object.

        Returns:
            Intent-specific return value.

        Raises:
            ValueError: If ``kind`` is unsupported.

        Boundary behavior:
            When an application service is attached to the node, this wrapper
            routes through ``DecisionAppService.dispatch_intent`` so all state
            mutations still flow through the single authoritative application
            entrypoint. The local legacy fallback remains only for older tests
            and lightweight harnesses that do not construct the full service.
        """
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
        if kind == 'chassis_state':
            self.cache_chassis_state(payload)
            return None
        if kind == 'system_status':
            return self.cache_system_status(payload)
        raise ValueError(f'unknown decision intent kind: {kind}')

    def complete_boot_transition(self) -> bool:
        """Complete BOOT mode and enter IDLE when appropriate.

        Args:
            None.

        Returns:
            ``True`` when the mode actually changed.

        Raises:
            None.
        """
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
        """Apply one mode transition under the serialized state boundary.

        Args:
            new_mode: Target logical mode.
            requested_by: Request source label used for audit output.
            reason: Human-readable transition reason.

        Returns:
            ``True`` when the mode actually changed.

        Raises:
            None.
        """
        changed = False

        def _mutation() -> None:
            nonlocal changed
            changed = self.apply_mode_transition_locked(new_mode, requested_by, reason)

        self._node._run_state_mutation('set_mode', _mutation)
        return changed

    def apply_mode_transition_locked(self, new_mode: str, requested_by: str, reason: str) -> bool:
        """Apply one mode transition while the caller already holds the state lock.

        Args:
            new_mode: Target mode.
            requested_by: Request source label.
            reason: Human-readable transition reason.

        Returns:
            ``True`` when the mode changed.

        Raises:
            None.
        """
        previous_mode = self._node.current_mode
        self._node._set_mode_locked(new_mode, requested_by, reason)
        return previous_mode != self._node.current_mode

    def reset_fault_transition(self, requested_by: str, reason: str) -> tuple[bool, str, bool]:
        """Clear a recoverable fault and return to IDLE when allowed.

        Args:
            requested_by: Reset request source label.
            reason: Human-readable reset reason.

        Returns:
            Tuple ``(success, message, mode_changed)``.

        Raises:
            None.
        """
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
        """Record one fault message and update fault history.

        Args:
            msg: Fault-like message.

        Returns:
            None.

        Raises:
            None.
        """
        def _mutation() -> None:
            self._node.last_fault = msg
            entry = f"{getattr(msg, 'code', '')}:{getattr(msg, 'level', '')}"
            self._node.context.fault_history.append(entry)
            if len(self._node.context.fault_history) > 10:
                self._node.context.fault_history = self._node.context.fault_history[-10:]

        self._node._run_state_mutation('record_fault', _mutation)

    def record_voice_command(self, command: str) -> None:
        """Cache one voice-command label for observability.

        Args:
            command: Raw voice command string.

        Returns:
            None.

        Raises:
            None.
        """
        self._node._run_state_mutation('record_voice_command', lambda: setattr(self._node.context, 'last_voice_command', str(command or '')))

    def record_target(self, msg: Any) -> Twist | None:
        """Record one target observation and update tracking counters.

        Args:
            msg: Vision-target message.

        Returns:
            Tracking command when the system is already in ``MODE_TRACK``;
            otherwise ``None``.

        Raises:
            None.
        """
        track_cmd: Twist | None = None

        def _mutation() -> None:
            nonlocal track_cmd
            self._node.last_target = msg
            self._node.context.track_target_valid = bool(getattr(msg, 'detected', False))
            self._node.context.last_target_type = str(getattr(msg, 'target_type', '') or '')
            if self._node.current_mode == MODE_PATROL and bool(getattr(msg, 'detected', False)):
                self._node.patrol_manager.note_detection(
                    target_type=str(getattr(msg, 'target_type', '') or ''),
                    confidence=float(getattr(msg, 'confidence', 0.0) or 0.0),
                )
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
        """Record the latest QR-code observation.

        Args:
            data: QR-code payload.

        Returns:
            None.

        Raises:
            None.
        """
        self._node._run_state_mutation('record_qrcode', lambda: setattr(self._node.context, 'last_qrcode', str(data or '')))

    def apply_runtime_overrides(self, params: dict[str, Any]) -> None:
        """Apply runtime-parameter overrides to cached decision state.

        Args:
            params: Effective runtime-parameter map.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            Invalid numeric values are ignored in favor of the last good values
            already stored on the track manager.
        """
        def _mutation() -> None:
            self._node._runtime_param_overrides = dict(params)
            self._node.track_manager.max_linear = self._coerce_float(params.get('maxLinearSpeed'), self._node.track_manager.max_linear)
            self._node.track_manager.max_angular = self._coerce_float(params.get('maxAngularSpeed'), self._node.track_manager.max_angular)
            self._node.track_manager.offset_deadband = self._coerce_float(params.get('trackOffsetDeadband'), self._node.track_manager.offset_deadband)

        self._node._run_state_mutation('apply_runtime_overrides', _mutation)

    def cache_chassis_state(self, msg: Any) -> None:
        """Cache one chassis-state message."""
        self._node._run_state_mutation('on_chassis_state', lambda: setattr(self._node, 'chassis_state', msg))

    def cache_system_status(self, msg: Any) -> Any | None:
        """Cache one system-status message and return the previous snapshot.

        Args:
            msg: New system-status message.

        Returns:
            Previous cached system-status message, if any.

        Raises:
            None.
        """
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
