from __future__ import annotations

"""Mode gating and safe-stop recovery helpers for the decision runtime."""

from typing import Any

from robot_contracts.bridge_contract import CommandContext
from robot_decision.mode_table import get_mode_spec
from robot_decision.recovery_policy import can_recover_from_safe_stop, recovery_summary
from robot_decision.transition_rules import can_transition, explain_transition
from robot_utils.constants import ALL_MODES, FAULT_LEVEL_ERROR, FAULT_LEVEL_FATAL, MODE_FAULT, MODE_PATROL, MODE_SAFE_STOP


class ModeGuard:
    """Encapsulate decision-layer mode gating and recovery semantics."""

    def __init__(self, node: Any) -> None:
        self._node = node

    def normalized_fault_level(self) -> str:
        """Return one normalized fault-severity label."""
        if self._node.last_fault is None:
            return 'info'
        level = str(getattr(self._node.last_fault, 'level', 'info') or 'info').lower()
        if level in {FAULT_LEVEL_FATAL, 'critical'}:
            return 'critical'
        if level in {FAULT_LEVEL_ERROR, 'error', 'warning', 'warn'}:
            return 'warning'
        return 'info'

    def link_ready(self) -> bool:
        """Return whether bridge and UART links are healthy."""
        status = self._node.system_status
        if status is None:
            return False
        return bool(getattr(status, 'wifi_ok', False) and getattr(status, 'uart_ok', False))

    def power_ready(self) -> bool:
        """Return whether power conditions permit motion."""
        status = self._node.system_status
        if status is None:
            return False
        return not bool(getattr(status, 'low_power_stop', False) or getattr(status, 'low_power_warn', False))

    def heartbeat_ready(self) -> bool:
        """Return whether the chassis heartbeat is healthy."""
        chassis = self._node.chassis_state
        if chassis is None:
            return False
        return bool(getattr(chassis, 'heartbeat_ok', False) and getattr(chassis, 'comm_ok', True))

    def manual_recovery_required(self) -> bool:
        """Return whether recovering from the current stop/fault needs manual acknowledgment."""
        if self._node.current_mode not in {MODE_SAFE_STOP, MODE_FAULT}:
            return False
        return bool(self.estop_active()) or bool(
            self._node.last_fault is not None and getattr(self._node.last_fault, 'level', '') == FAULT_LEVEL_ERROR
        )

    def estop_active(self) -> bool:
        """Return whether the chassis emergency-stop signal is active."""
        return bool(self._node.chassis_state is not None and getattr(self._node.chassis_state, 'estop', False))

    def safe_stop_recovery_status(self, *, require_manual_confirm: bool) -> tuple[bool, str | None]:
        """Evaluate whether the system may recover from SAFE_STOP.

        Args:
            require_manual_confirm: Whether manual acknowledgment is required for
                the current evaluation.

        Returns:
            Tuple ``(recoverable, blocked_reason)``.

        Raises:
            None.
        """
        estop_active = self.estop_active()
        link_ok = self.link_ready()
        power_ok = self.power_ready()
        heartbeat_ok = self.heartbeat_ready()
        manual_confirmed = self._node._safe_stop_manual_confirmed if require_manual_confirm else True
        if can_recover_from_safe_stop(
            estop_active=estop_active,
            link_ok=link_ok,
            last_fault=self._node.last_fault,
            power_ok=power_ok,
            heartbeat_ok=heartbeat_ok,
            manual_confirmed=manual_confirmed,
        ):
            return True, None
        return False, recovery_summary(
            estop_active,
            link_ok,
            self._node.last_fault,
            power_ok=power_ok,
            heartbeat_ok=heartbeat_ok,
            manual_confirmed=manual_confirmed,
        )

    def system_ready_for_patrol(self) -> bool:
        """Return whether the system is ready to enter PATROL."""
        if not bool(self._node.get_parameter('require_ready_for_patrol').value):
            return True
        return self.link_ready() and self.power_ready()

    def command_context(self) -> CommandContext:
        """Build the bridge-facing command capability context snapshot."""
        safe_stop_recoverable, blocked_reason = self.safe_stop_recovery_status(require_manual_confirm=False)
        return CommandContext(
            current_mode=self._node.current_mode,
            bridge_connected=self.link_ready() and self.heartbeat_ready(),
            low_power_warning=bool(
                self._node.system_status is not None and (
                    getattr(self._node.system_status, 'low_power_warn', False)
                    or getattr(self._node.system_status, 'low_power_stop', False)
                )
            ),
            fault_code=self._node.last_fault.code if self._node.last_fault is not None and getattr(self._node.last_fault, 'code', '') else None,
            fault_level=self.normalized_fault_level(),
            estop_active=self.estop_active(),
            safe_stop_active=self._node.current_mode in {MODE_SAFE_STOP, MODE_FAULT},
            safe_stop_recoverable=safe_stop_recoverable,
            safe_stop_requires_manual_ack=self.manual_recovery_required(),
            safe_stop_blocked_reason=blocked_reason,
        )

    def request_mode_change(self, requested_mode: str, requested_by: str, reason: str) -> tuple[bool, str]:
        """Validate and apply one mode-change request.

        Args:
            requested_mode: Target logical mode.
            requested_by: Request source label.
            reason: Human-readable transition reason.

        Returns:
            Tuple ``(success, message)``.

        Raises:
            None.

        Boundary behavior:
            This helper mutates the mode state under the node lock but does not
            publish ROS side effects. Publishing is owned by the application
            service and ``DecisionSideEffects``.
        """
        with self._node.state_guard():
            if requested_mode not in ALL_MODES:
                return False, f'unknown mode: {requested_mode}'
            spec = get_mode_spec(requested_mode)
            if spec.requires_link_ok and not self.system_ready_for_patrol():
                return False, 'system_not_ready'
            if self._node.current_mode == MODE_SAFE_STOP and requested_mode in {'IDLE', 'MANUAL'}:
                manual_requester = requested_by not in {'decision', 'fault', 'system', 'action', 'vision', 'app_service'}
                previous_manual_confirmation = self._node._safe_stop_manual_confirmed
                self._node._safe_stop_manual_confirmed = bool(manual_requester)
                safe_stop_recoverable, blocked_reason = self.safe_stop_recovery_status(require_manual_confirm=True)
                if not safe_stop_recoverable:
                    self._node._safe_stop_manual_confirmed = previous_manual_confirmation
                    return False, blocked_reason or 'safe_stop_not_recoverable'
            if self._node.current_mode == MODE_FAULT and requested_mode != 'IDLE':
                return False, 'fault mode can only reset to IDLE'
            if self._node.current_mode == MODE_PATROL and requested_mode != MODE_PATROL:
                manual_requester = requested_by not in {'decision', 'fault', 'system', 'action', 'vision', 'app_service'}
                if manual_requester and self._node.context.navigation_state in {'failed', 'cancelled'}:
                    return False, 'manual_interrupt_deferred_until_navigation_stabilizes'
            if not can_transition(self._node.current_mode, requested_mode):
                return False, explain_transition(self._node.current_mode, requested_mode)
            self._node._set_mode_locked(requested_mode, requested_by, reason)
        return True, 'mode changed'
