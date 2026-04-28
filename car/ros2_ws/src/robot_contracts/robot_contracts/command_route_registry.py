from __future__ import annotations

"""Authoritative command-route registry for operator-facing write paths.

The registry now feeds runtime timeout budgets, denial detail codes, handler
alignment checks, generated artifacts, and governance scripts so bridge/API
layers use the same command-route matrix rather than duplicating it in docs.
"""

from dataclasses import dataclass
from typing import Any

from robot_contracts.capabilities import COMMAND_LIFECYCLE_STATUSES, COMMAND_TYPES
from robot_contracts.command_policy import COMMAND_TARGET_MODE, command_allowed_modes
from robot_contracts.feature_admission import feature_admission_payload


@dataclass(frozen=True, slots=True)
class CommandRouteEntry:
    """Declarative route metadata for one command type.

    Args:
        command_type: Bridge command identifier.
        entry_surfaces: Operator ingress surfaces allowed to emit the command.
        session_policy: Authoritative session-policy contract governing writes.
        dispatch_transport: Transport used from API facade to authoritative bridge runtime.
        bridge_handler: Web-bridge handler method responsible for dispatch.
        target_nodes: Runtime owners expected to consume or apply the command.
        timeout_budget_ms: End-to-end budget before the route is considered timed out.
        fallback_paths: Ordered protocol/runtime fallback paths when the preferred route is unavailable.
        deny_conditions: Human-facing conditions that deterministically deny the route before application.
        rollback_paths: Safe rollback / interruption paths operators can use when a route misbehaves.
        terminal_lifecycle_statuses: Terminal lifecycle statuses expected for the command.
        notes: Supplemental operator/auditor notes.

    Returns:
        Immutable command-route entry.

    Raises:
        None.
    """

    command_type: str
    entry_surfaces: tuple[str, ...]
    session_policy: str
    dispatch_transport: str
    bridge_handler: str
    target_nodes: tuple[str, ...]
    timeout_budget_ms: int
    fallback_paths: tuple[str, ...]
    deny_conditions: tuple[str, ...]
    rollback_paths: tuple[str, ...]
    terminal_lifecycle_statuses: tuple[str, ...]
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            'commandType': self.command_type,
            'entrySurfaces': list(self.entry_surfaces),
            'sessionPolicy': self.session_policy,
            'dispatchTransport': self.dispatch_transport,
            'bridgeHandler': self.bridge_handler,
            'targetNodes': list(self.target_nodes),
            'timeoutBudgetMs': self.timeout_budget_ms,
            'fallbackPaths': list(self.fallback_paths),
            'denyConditions': list(self.deny_conditions),
            'rollbackPaths': list(self.rollback_paths),
            'allowedModes': list(command_allowed_modes(self.command_type)),
            'targetMode': COMMAND_TARGET_MODE.get(self.command_type),
            'terminalLifecycleStatuses': list(self.terminal_lifecycle_statuses),
            'notes': list(self.notes),
        }


def _entry(
    command_type: str,
    *,
    bridge_handler: str,
    target_nodes: tuple[str, ...],
    timeout_budget_ms: int,
    fallback_paths: tuple[str, ...],
    deny_conditions: tuple[str, ...],
    rollback_paths: tuple[str, ...],
    notes: tuple[str, ...] = (),
) -> CommandRouteEntry:
    return CommandRouteEntry(
        command_type=command_type,
        entry_surfaces=('frontend_api_facade',),
        session_policy='robot_contracts.command_policy:resolve_session_policy',
        dispatch_transport='robot_api_server -> internal_command_socket -> robot_web_bridge',
        bridge_handler=bridge_handler,
        target_nodes=target_nodes,
        timeout_budget_ms=timeout_budget_ms,
        fallback_paths=fallback_paths,
        deny_conditions=deny_conditions,
        rollback_paths=rollback_paths,
        terminal_lifecycle_statuses=('applied', 'completed', 'rejected', 'denied', 'timeout', 'cancelled'),
        notes=notes,
    )


_COMMAND_ROUTE_REGISTRY: dict[str, CommandRouteEntry] = {
    'set_mode': _entry(
        'set_mode',
        bridge_handler='handle_set_mode',
        target_nodes=('robot_decision', 'robot_control'),
        timeout_budget_ms=3000,
        fallback_paths=(),
        deny_conditions=('readonly_session', 'observer_surface', 'mode_transition_guard_rejected'),
        rollback_paths=('set_mode:IDLE', 'estop'),
    ),
    'teleop_cmd': _entry(
        'teleop_cmd',
        bridge_handler='handle_teleop',
        target_nodes=('robot_control', 'robot_bridge'),
        timeout_budget_ms=250,
        fallback_paths=('latest_only_supersession',),
        deny_conditions=('readonly_session', 'observer_surface', 'mode_not_manual'),
        rollback_paths=('stop_now', 'estop', 'disable_operator_session'),
        notes=('latest-only queue replacement is authoritative for teleop_cmd.',),
    ),
    'stop_now': _entry(
        'stop_now',
        bridge_handler='handle_stop_now',
        target_nodes=('robot_control',),
        timeout_budget_ms=800,
        fallback_paths=(),
        deny_conditions=('readonly_session', 'observer_surface'),
        rollback_paths=('estop',),
    ),
    'estop': _entry(
        'estop',
        bridge_handler='handle_estop',
        target_nodes=('robot_control', 'robot_decision'),
        timeout_budget_ms=1000,
        fallback_paths=(),
        deny_conditions=('readonly_session', 'observer_surface'),
        rollback_paths=('resume_from_safe_stop', 'reset_fault'),
        notes=('Emergency stop is intentionally permissive in mode coverage but still requires authoritative write access.',),
    ),
    'resume_from_safe_stop': _entry(
        'resume_from_safe_stop',
        bridge_handler='handle_resume_from_safe_stop',
        target_nodes=('robot_decision', 'robot_control'),
        timeout_budget_ms=2500,
        fallback_paths=(),
        deny_conditions=('readonly_session', 'observer_surface', 'safe_stop_not_recoverable'),
        rollback_paths=('estop', 'set_mode:SAFE_STOP'),
    ),
    'start_patrol': _entry(
        'start_patrol',
        bridge_handler='handle_start_patrol',
        target_nodes=('robot_decision', 'robot_navigation'),
        timeout_budget_ms=4000,
        fallback_paths=(),
        deny_conditions=('readonly_session', 'observer_surface', 'navigation_lane_unavailable', 'mode_transition_guard_rejected'),
        rollback_paths=('pause_patrol', 'stop_patrol', 'switch_provider_to_simple_nav_provider'),
    ),
    'pause_patrol': _entry(
        'pause_patrol',
        bridge_handler='handle_pause_patrol',
        target_nodes=('robot_decision', 'robot_navigation'),
        timeout_budget_ms=3000,
        fallback_paths=('cancel_action_then_set_mode_idle',),
        deny_conditions=('readonly_session', 'observer_surface', 'mode_guard_rejected'),
        rollback_paths=('stop_patrol', 'set_mode:IDLE'),
    ),
    'stop_patrol': _entry(
        'stop_patrol',
        bridge_handler='handle_stop_patrol',
        target_nodes=('robot_decision', 'robot_navigation'),
        timeout_budget_ms=3000,
        fallback_paths=('cancel_action_then_set_mode_idle',),
        deny_conditions=('readonly_session', 'observer_surface', 'mode_guard_rejected'),
        rollback_paths=('set_mode:IDLE', 'switch_provider_to_simple_nav_provider'),
    ),
    'apply_param_draft': _entry(
        'apply_param_draft',
        bridge_handler='handle_apply_param_draft',
        target_nodes=('runtime_param_coordinator', 'robot_control', 'robot_decision', 'robot_monitor'),
        timeout_budget_ms=6000,
        fallback_paths=(),
        deny_conditions=('readonly_session', 'observer_surface', 'empty_runtime_param_patch'),
        rollback_paths=('apply_param_profile:last_known_good',),
    ),
    'apply_param_profile': _entry(
        'apply_param_profile',
        bridge_handler='handle_apply_param_profile',
        target_nodes=('runtime_param_coordinator', 'robot_control', 'robot_decision', 'robot_monitor'),
        timeout_budget_ms=6000,
        fallback_paths=(),
        deny_conditions=('readonly_session', 'observer_surface', 'unknown_runtime_profile'),
        rollback_paths=('apply_param_profile:last_known_good',),
    ),
    'speak_fixed_text': _entry(
        'speak_fixed_text',
        bridge_handler='handle_speak_fixed_text',
        target_nodes=('robot_voice',),
        timeout_budget_ms=4000,
        fallback_paths=('topic:/robot/speak_req',),
        deny_conditions=('readonly_session', 'observer_surface', 'empty_speak_text', 'invalid_speak_priority'),
        rollback_paths=('disable_voice_ingress_route',),
        notes=('Topic route proves publication into robot_voice only; physical speaker output remains target acceptance evidence.',),
    ),
    'reset_fault': _entry(
        'reset_fault',
        bridge_handler='handle_reset_fault',
        target_nodes=('robot_decision', 'robot_control'),
        timeout_budget_ms=3000,
        fallback_paths=(),
        deny_conditions=('readonly_session', 'observer_surface', 'fault_not_resettable'),
        rollback_paths=('estop',),
    ),
    'save_snapshot': _entry(
        'save_snapshot',
        bridge_handler='handle_save_snapshot',
        target_nodes=('robot_vision',),
        timeout_budget_ms=8000,
        fallback_paths=('action:/robot/actions/save_snapshot', 'service:/robot/save_snapshot'),
        deny_conditions=('readonly_session', 'observer_surface'),
        rollback_paths=('retry_snapshot_capture',),
        notes=('Action route is preferred; service fallback remains for compatibility.',),
    ),
}


def command_route_registry_payload() -> dict[str, dict[str, Any]]:
    """Serialize the command-route registry."""
    return {command: entry.to_dict() for command, entry in sorted(_COMMAND_ROUTE_REGISTRY.items())}



def command_route_entry(command_type: str) -> CommandRouteEntry | None:
    """Return the declarative command-route entry for one command type."""
    normalized = str(command_type or '').strip()
    return _COMMAND_ROUTE_REGISTRY.get(normalized)


def command_route_timeout_budget_ms(command_type: str, *, default_ms: int | None = None) -> int:
    """Return the runtime timeout budget for one command type."""
    entry = command_route_entry(command_type)
    if entry is not None:
        return int(entry.timeout_budget_ms)
    if default_ms is not None:
        return max(1, int(default_ms))
    return 10000


def command_route_handler_name(command_type: str) -> str | None:
    """Return the expected bridge handler name for one command type."""
    entry = command_route_entry(command_type)
    return None if entry is None else str(entry.bridge_handler)


def command_route_denial_detail(command_type: str, message: str, *, source_surface: str = '', session_write_enabled: bool | None = None) -> str:
    """Classify one runtime denial/rejection into a stable governance detail code.

    The returned code intentionally reuses registry ``deny_conditions`` / fallback
    tokens so runtime envelopes, audits, and governance checks speak the same
    vocabulary. Human-readable ``message`` remains unchanged for operators.
    """
    normalized = str(command_type or '').strip()
    lowered = str(message or '').strip().lower()
    source_surface_normalized = str(source_surface or '').strip()
    if session_write_enabled is False:
        return 'readonly_session'
    if source_surface_normalized == 'bridge_observer_surface':
        return 'observer_surface'
    if 'observer surface' in lowered or 'observer-only' in lowered or 'observer only' in lowered:
        return 'observer_surface'
    if 'read-only' in lowered or 'read only' in lowered or 'command writes are blocked' in lowered or 'session role' in lowered:
        return 'readonly_session'
    if normalized == 'teleop_cmd' and 'manual mode' in lowered:
        return 'mode_not_manual'
    if normalized in {'start_patrol', 'set_mode'} and ('cannot transition' in lowered or 'already in requested mode' in lowered or 'target mode must be non-empty' in lowered):
        return 'mode_transition_guard_rejected'
    if normalized in {'pause_patrol', 'stop_patrol'} and 'is not allowed while mode=' in lowered:
        return 'mode_guard_rejected'
    if normalized == 'resume_from_safe_stop' and ('safe stop recovery' in lowered or 'recover' in lowered or 'blocked' in lowered):
        return 'safe_stop_not_recoverable'
    if normalized == 'start_patrol' and ('action unavailable' in lowered or 'navigation provider' in lowered or 'experimental provider' in lowered):
        return 'navigation_lane_unavailable'
    if normalized == 'apply_param_draft' and ('patch must not be empty' in lowered or 'requires params mapping' in lowered):
        return 'empty_runtime_param_patch'
    if normalized == 'apply_param_profile' and ('requires profilename' in lowered or 'unsupported runtime parameter profile' in lowered):
        return 'unknown_runtime_profile'
    if normalized == 'reset_fault' and ('is not allowed while mode=' in lowered or 'reset fault' in lowered and 'failed' in lowered):
        return 'fault_not_resettable'
    entry = command_route_entry(normalized)
    if entry is not None:
        for deny_code in entry.deny_conditions:
            if str(deny_code) in lowered:
                return str(deny_code)
        for fallback in entry.fallback_paths:
            if str(fallback).replace(':', ' ').replace('_', ' ') in lowered:
                return str(fallback)
    return ''


def validate_command_route_registry() -> list[str]:
    """Validate coverage and cross-registry alignment.

    Returns:
        List of validation errors. Empty means valid.

    Raises:
        None.
    """
    errors: list[str] = []
    payload = feature_admission_payload()
    feature_by_command: dict[str, dict[str, Any]] = {}
    for feature in payload.values():
        for command in feature.get('commands', []):
            feature_by_command[str(command)] = feature

    for command in COMMAND_TYPES:
        if command not in _COMMAND_ROUTE_REGISTRY:
            errors.append(f'missing_command_route:{command}')
            continue
        entry = _COMMAND_ROUTE_REGISTRY[command]
        if entry.timeout_budget_ms <= 0:
            errors.append(f'{command}:invalid_timeout_budget_ms')
        if not entry.target_nodes:
            errors.append(f'{command}:missing_target_nodes')
        if not entry.entry_surfaces:
            errors.append(f'{command}:missing_entry_surfaces')
        if command not in feature_by_command:
            errors.append(f'{command}:missing_feature_admission_owner')
            continue
        feature_entry = feature_by_command[command]
        declared_entry_surfaces = tuple(str(item) for item in feature_entry.get('entrySurfaces', []))
        if tuple(entry.entry_surfaces) != declared_entry_surfaces:
            errors.append(
                f'{command}:entry_surface_mismatch:route={list(entry.entry_surfaces)}:feature={list(declared_entry_surfaces)}'
            )
        authoritative_nodes = tuple(str(item) for item in feature_entry.get('authoritativeNodes', []))
        if authoritative_nodes and not set(authoritative_nodes).intersection(entry.target_nodes):
            errors.append(
                f'{command}:authoritative_node_mismatch:route={list(entry.target_nodes)}:feature={list(authoritative_nodes)}'
            )
        invalid_terminal = [status for status in entry.terminal_lifecycle_statuses if status not in COMMAND_LIFECYCLE_STATUSES]
        if invalid_terminal:
            errors.append(f'{command}:invalid_terminal_lifecycle_statuses:{invalid_terminal}')
    for command in sorted(_COMMAND_ROUTE_REGISTRY):
        if command not in COMMAND_TYPES:
            errors.append(f'unsupported_command_route:{command}')
    return errors
