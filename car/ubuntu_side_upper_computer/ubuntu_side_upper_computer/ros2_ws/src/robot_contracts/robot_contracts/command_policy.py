from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from robot_contracts.capabilities import COMMAND_TYPES

COMMAND_PERMISSION_MATRIX: dict[str, tuple[str, ...]] = {
    'set_mode': ('IDLE', 'MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT'),
    'teleop_cmd': ('MANUAL',),
    'stop_now': ('MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT', 'IDLE'),
    'estop': ('IDLE', 'MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT', 'BOOT'),
    'resume_from_safe_stop': ('SAFE_STOP',),
    'start_patrol': ('IDLE',),
    'pause_patrol': ('PATROL', 'TRACK'),
    'stop_patrol': ('PATROL', 'TRACK', 'MANUAL', 'SAFE_STOP'),
    'set_param': ('IDLE', 'MANUAL', 'PATROL', 'TRACK'),
    'apply_param_profile': ('IDLE', 'MANUAL'),
    'speak_fixed_text': ('BOOT', 'IDLE', 'MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT'),
    'reset_fault': ('FAULT', 'SAFE_STOP'),
    'save_snapshot': ('IDLE', 'MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT'),
}

MODE_TRANSITION_TARGETS: dict[str, tuple[str, ...]] = {
    'BOOT': ('IDLE',),
    'IDLE': ('MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT'),
    'MANUAL': ('IDLE', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT'),
    'PATROL': ('IDLE', 'MANUAL', 'TRACK', 'SAFE_STOP', 'FAULT'),
    'TRACK': ('IDLE', 'MANUAL', 'PATROL', 'SAFE_STOP', 'FAULT'),
    'SAFE_STOP': ('IDLE', 'MANUAL', 'FAULT'),
    'FAULT': ('IDLE', 'SAFE_STOP'),
}

COMMAND_TARGET_MODE: dict[str, str] = {
    'start_patrol': 'PATROL',
    'pause_patrol': 'IDLE',
    'stop_patrol': 'IDLE',
    'resume_from_safe_stop': 'IDLE',
    'estop': 'SAFE_STOP',
}


@dataclass(frozen=True, slots=True)
class CommandContext:
    """Runtime context used to evaluate command and mode access.

    Args:
        current_mode: Current authoritative robot mode.
        bridge_connected: Whether the bridge transport is considered healthy.
        low_power_warning: Whether low power is currently asserted.
        fault_code: Active fault code, if any.
        fault_level: Active fault level, normalized to frontend-compatible labels.
        estop_active: Whether emergency stop is latched.
        safe_stop_active: Whether safe-stop is active.
        safe_stop_recoverable: Whether SAFE_STOP can recover to an operational mode.
        safe_stop_requires_manual_ack: Whether recovery still requires an explicit operator confirmation.
        safe_stop_blocked_reason: Human-readable reason when SAFE_STOP recovery is blocked.

    Returns:
        CommandContext instance.

    Raises:
        None.
    """

    current_mode: str = 'BOOT'
    bridge_connected: bool = False
    low_power_warning: bool = False
    fault_code: str | None = None
    fault_level: str = 'info'
    estop_active: bool = False
    safe_stop_active: bool = False
    safe_stop_recoverable: bool = True
    safe_stop_requires_manual_ack: bool = False
    safe_stop_blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ContractCheckResult:
    ok: bool
    reason: str = 'ok'



def command_allowed_modes(command_type: str) -> tuple[str, ...]:
    """Return the permitted source modes for one command type."""
    return COMMAND_PERMISSION_MATRIX.get(str(command_type or '').strip(), ())



def allowed_target_modes(context: CommandContext) -> dict[str, str]:
    """Resolve backend-authoritative target modes allowed from the current state.

    Args:
        context: Current command-evaluation context.

    Returns:
        Mapping of allowed target mode to human-readable rationale.

    Raises:
        None.
    """
    base_targets = MODE_TRANSITION_TARGETS.get(context.current_mode, ())
    allowed: dict[str, str] = {mode: 'allowed' for mode in base_targets}
    if not allowed:
        return allowed

    if context.estop_active:
        for mode in tuple(allowed):
            if mode not in {'SAFE_STOP', 'IDLE'}:
                allowed.pop(mode, None)
        if context.safe_stop_active:
            allowed['FAULT'] = 'fault escalation allowed while SAFE_STOP is latched'
        return allowed

    if context.safe_stop_active and context.current_mode == 'SAFE_STOP' and not context.safe_stop_recoverable:
        for mode in ('IDLE', 'MANUAL'):
            allowed.pop(mode, None)
        if context.safe_stop_blocked_reason:
            allowed['FAULT'] = context.safe_stop_blocked_reason

    if context.fault_code and str(context.fault_level).lower() == 'critical':
        for mode in tuple(allowed):
            if mode not in {'FAULT', 'SAFE_STOP', 'IDLE'}:
                allowed.pop(mode, None)

    if not context.bridge_connected:
        for mode in ('MANUAL', 'PATROL', 'TRACK'):
            allowed.pop(mode, None)

    if context.low_power_warning:
        for mode in ('PATROL', 'TRACK'):
            allowed.pop(mode, None)

    return allowed



def mode_transition_allowed(context: CommandContext, target_mode: str) -> ContractCheckResult:
    """Check whether a target mode is allowed under the current runtime context.

    Args:
        context: Current command-evaluation context.
        target_mode: Requested target mode.

    Returns:
        ``ContractCheckResult`` describing whether the target mode is allowed.

    Raises:
        None.
    """
    normalized = str(target_mode or '').strip().upper()
    if not normalized:
        return ContractCheckResult(False, 'target mode must be non-empty')
    if normalized == context.current_mode:
        return ContractCheckResult(False, 'already in requested mode')
    allowed = allowed_target_modes(context)
    if normalized not in allowed:
        blocked_reason = context.safe_stop_blocked_reason if context.current_mode == 'SAFE_STOP' and not context.safe_stop_recoverable else None
        if blocked_reason and normalized in {'IDLE', 'MANUAL'}:
            return ContractCheckResult(False, blocked_reason)
        allowed_list = ', '.join(sorted(allowed)) if allowed else '(none)'
        return ContractCheckResult(False, f'{context.current_mode} cannot transition to {normalized}; allowed targets: {allowed_list}')
    return ContractCheckResult(True, allowed[normalized])



def command_guard(command_type: str, context: CommandContext, *, payload: Mapping[str, Any] | None = None) -> ContractCheckResult:
    """Evaluate whether a bridge command is admissible in the current runtime context.

    Args:
        command_type: Command type to evaluate.
        context: Current command-evaluation context.
        payload: Optional command payload.

    Returns:
        ``ContractCheckResult`` describing whether the command is allowed.

    Raises:
        None.
    """
    normalized = str(command_type or '').strip()
    allowed_modes = command_allowed_modes(normalized)
    if not allowed_modes:
        return ContractCheckResult(False, f'unsupported command: {normalized}')
    if context.current_mode not in allowed_modes:
        return ContractCheckResult(False, f'{normalized} is not allowed while mode={context.current_mode}; allowed modes: {", ".join(allowed_modes)}')
    if normalized == 'teleop_cmd' and context.current_mode != 'MANUAL':
        return ContractCheckResult(False, 'teleop is only allowed in MANUAL mode')
    if normalized == 'resume_from_safe_stop' and not context.safe_stop_recoverable:
        return ContractCheckResult(False, context.safe_stop_blocked_reason or 'safe stop recovery is currently blocked')
    if normalized == 'start_patrol' and not mode_transition_allowed(context, 'PATROL').ok:
        return mode_transition_allowed(context, 'PATROL')
    if normalized == 'set_mode':
        target_mode = str((payload or {}).get('mode', '')).strip().upper()
        return mode_transition_allowed(context, target_mode)
    target_mode = COMMAND_TARGET_MODE.get(normalized)
    if target_mode:
        return mode_transition_allowed(context, target_mode)
    return ContractCheckResult(True, 'ok')



def command_capability_snapshot(context: CommandContext) -> dict[str, Any]:
    """Build a frontend-consumable command capability snapshot.

    Args:
        context: Current command-evaluation context.

    Returns:
        Dictionary containing allowed target modes, command permissions and recovery hints.

    Raises:
        None.
    """
    allowed_modes = allowed_target_modes(context)
    permissions: dict[str, dict[str, Any]] = {}
    for command in COMMAND_TYPES:
        if command == 'set_mode':
            permissions[command] = {
                'allowed': bool(allowed_modes),
                'reason': 'ok' if allowed_modes else 'no target modes available from current state',
            }
            continue
        result = command_guard(command, context)
        permissions[command] = {
            'allowed': bool(result.ok),
            'reason': result.reason,
        }
    return {
        'allowedTargetModes': list(sorted(allowed_modes.keys())),
        'modeReasons': {key: value for key, value in allowed_modes.items()},
        'commandPermissions': permissions,
        'safeStopRecoverable': bool(context.safe_stop_recoverable),
        'safeStopRequiresManualAck': bool(context.safe_stop_requires_manual_ack),
        'safeStopBlockedReason': context.safe_stop_blocked_reason,
    }
