from __future__ import annotations

"""Authoritative command application layer for robot web bridge adapters.

This module centralizes command extraction, session-policy overlay, contract
checking, handler lookup, and dispatch. Transport adapters keep their current
entrypoints, but command semantics now live in one application-layer service so
future HTTP / websocket / internal-socket adapters do not reimplement guard
logic.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from robot_contracts.command_policy import SessionPolicy, apply_session_policy_to_context
from robot_contracts.bridge_contract import command_guard


@dataclass(frozen=True)
class ResolvedCommandRequest:
    """Normalized command request ready for contract evaluation and dispatch.

    Args:
        command_type: Canonical command identifier.
        event_id: Stable command/event identifier.
        trace_id: Optional end-to-end trace identifier.
        payload: Command payload mapping.
        reason: Human-readable audit reason.
        operator_id: Operator/session identifier for downstream services/actions.
        session_policy: Optional explicit session policy overlay.
    """

    command_type: str
    event_id: str
    trace_id: str
    payload: Mapping[str, Any]
    reason: str
    operator_id: str
    session_policy: SessionPolicy | None


class CommandApplicationService:
    """Single command application layer shared by all bridge command adapters."""

    def __init__(self, router: Any, handlers: Mapping[str, Any]) -> None:
        self._router = router
        self._handlers = dict(handlers)

    @staticmethod
    def _resolve_session_policy(raw_session: Mapping[str, Any] | None) -> SessionPolicy | None:
        if not isinstance(raw_session, Mapping) or not raw_session:
            return None
        return SessionPolicy(
            role=str(raw_session.get('role', 'observer') or 'observer'),
            requested_role=str(raw_session.get('requested_role', raw_session.get('role', 'observer')) or 'observer'),
            session_id=str(raw_session.get('session_id', '') or ''),
            write_enabled=bool(raw_session.get('write_enabled', False)),
            reason=str(raw_session.get('reason', '') or 'observer session is read-only'),
            source=str(raw_session.get('source', 'bridge_ws') or 'bridge_ws'),
            authenticated=bool(raw_session.get('authenticated', False)),
        )

    def resolve(self, cmd: Mapping[str, Any]) -> ResolvedCommandRequest:
        """Normalize one transport-level command envelope.

        Raises:
            ValueError: When the incoming command envelope lacks a command type.
        """
        command_type = str(cmd.get('type', '')).strip()
        if not command_type:
            raise ValueError('command type is empty')
        payload = cmd.get('payload', {}) if isinstance(cmd.get('payload'), Mapping) else {}
        return ResolvedCommandRequest(
            command_type=command_type,
            event_id=str(cmd.get('event_id', '') or 'frontend-event'),
            trace_id=str(cmd.get('trace_id', '') or ''),
            payload=payload,
            reason=str(cmd.get('reason', 'frontend_command')),
            operator_id=str(cmd.get('operator_id', 'frontend-console')),
            session_policy=self._resolve_session_policy(cmd.get('session_policy') if isinstance(cmd, Mapping) else None),
        )

    def dispatch(self, cmd: Mapping[str, Any]) -> None:
        """Apply one normalized command request through the authoritative contract.

        Boundary behavior:
            Invalid session overlays, unsupported commands, and mode/policy guard
            failures are rejected here before any command-family handler runs.
        """
        try:
            request = self.resolve(cmd)
        except ValueError as exc:
            self._router._deny(str(cmd.get('event_id', '') or 'frontend-event'), 'unknown', str(exc), trace_id=str(cmd.get('trace_id', '') or ''), detail='unsupported_command')
            return

        context = self._router.node.build_command_context()
        if request.session_policy is not None:
            context = apply_session_policy_to_context(context, request.session_policy)
        guard = command_guard(request.command_type, context, payload=request.payload)
        if not guard.ok:
            self._router._deny(request.event_id, request.command_type, guard.reason, trace_id=request.trace_id, detail=guard.detail_code)
            return

        handler = self._handlers.get(request.command_type)
        if handler is None:
            self._router._deny(request.event_id, request.command_type, f'unsupported command: {request.command_type}', trace_id=request.trace_id, detail='unsupported_command')
            return
        handler(
            meta=self._router._make_action_binding_from_request(request),
            payload=request.payload,
            reason=request.reason,
            operator_id=request.operator_id,
        )
