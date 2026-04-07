from __future__ import annotations

"""Ingress-side websocket command handling for the web bridge."""

import json
from typing import Any, Mapping

from robot_contracts.bridge_contract import validate_outbound_command_type
from robot_utils.error_policy import classify_exception, publish_policy_outcome


class IngressService:
    """Handle websocket ingress validation, admission, and router dispatch.

    Args:
        node: Full bridge node or compatible runtime double.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self, *, node: Any) -> None:
        self._node = node

    def _record_trace_id(self, trace_id: str) -> None:
        if not trace_id:
            return
        store = getattr(self._node, 'state_store', None)
        if store is not None:
            store.record_trace_id(trace_id)
            return
        state = getattr(self._node, 'state', None)
        if state is not None:
            setattr(state, 'last_trace_id', trace_id)
        sync = getattr(self._node, '_sync_snapshot_cache', None)
        if callable(sync):
            sync()

    def _record_phase(self, event_id: str, command_type: str, phase: str, status: str, message: str, *, trace_id: str = '', extra: Mapping[str, Any] | None = None) -> None:
        recorder = getattr(self._node, 'record_command_phase', None)
        if callable(recorder):
            recorder(event_id, command_type, phase, status, message, trace_id=trace_id, extra=extra)
            return
        self._record_trace_id(trace_id)
        timeline = getattr(getattr(self._node, 'state', None), 'command_timeline', None)
        if timeline is None:
            return
        item = {
            'commandId': event_id,
            'commandType': command_type,
            'phase': phase,
            'status': status,
            'message': message,
            'traceId': trace_id or None,
            'ts': self._node.now_iso() if hasattr(self._node, 'now_iso') else '',
        }
        if extra:
            item.update(dict(extra))
        timeline.appendleft(item)
        sync = getattr(self._node, '_sync_snapshot_cache', None)
        if callable(sync):
            sync()

    async def handle_ws_message(self, raw: str) -> None:
        """Validate and enqueue one websocket command envelope.

        Args:
            raw: Raw websocket message payload.

        Returns:
            None.

        Raises:
            None. Malformed envelopes are rejected with audit + policy outcomes.
        """
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            publish_policy_outcome(
                self._node,
                outcome=classify_exception(
                    'web_bridge.ws',
                    exc,
                    code='WEB_BRIDGE_MALFORMED_JSON',
                    operator_message=f'malformed command json: {exc.msg}',
                ),
                event_pub=self._node.event_pub,
            )
            self._node.audit_command('frontend-event', 'unknown', 'denied', f'malformed json: {exc.msg}')
            return
        if not isinstance(event, dict):
            publish_policy_outcome(
                self._node,
                outcome=classify_exception(
                    'web_bridge.ws',
                    TypeError('root must be an object'),
                    code='WEB_BRIDGE_ENVELOPE_INVALID',
                    operator_message='malformed command envelope: root must be an object',
                ),
                event_pub=self._node.event_pub,
            )
            self._node.audit_command('frontend-event', 'unknown', 'denied', 'malformed command envelope: root must be an object')
            return
        event_type = str(event.get('type', ''))
        trace_id = str(event.get('traceId', '') or '')
        event_id = str(event.get('eventId', 'frontend-event'))
        self._record_trace_id(trace_id)
        self._record_phase(
            event_id,
            event_type or 'unknown',
            'received',
            'queued',
            'frontend command received',
            trace_id=trace_id,
        )
        command_check = validate_outbound_command_type(event_type)
        if not command_check.ok:
            self._node.audit_command(event_id, event_type, 'denied', command_check.reason)
            self._record_phase(
                event_id,
                event_type or 'unknown',
                'validated',
                'denied',
                command_check.reason,
                trace_id=trace_id,
            )
            self._node.send_ack(event_id, 'denied', command_check.reason, trace_id=trace_id)
            return
        raw_payload = event.get('payload', {})
        if raw_payload is None:
            payload: dict[str, Any] = {}
        elif isinstance(raw_payload, dict):
            payload = raw_payload
        else:
            reason = 'malformed command envelope: payload must be an object when present'
            self._node.audit_command(event_id, event_type, 'denied', reason)
            self._record_phase(
                event_id,
                event_type or 'unknown',
                'validated',
                'denied',
                reason,
                trace_id=trace_id,
            )
            self._node.send_ack(event_id, 'denied', reason, trace_id=trace_id)
            publish_policy_outcome(
                self._node,
                outcome=classify_exception(
                    'web_bridge.ws',
                    TypeError('payload must be an object when present'),
                    code='WEB_BRIDGE_ENVELOPE_INVALID',
                    operator_message=reason,
                ),
                event_pub=self._node.event_pub,
            )
            return
        admission = self._node.dispatcher.enqueue(
            {
                'type': event_type,
                'event_id': event_id,
                'trace_id': trace_id,
                'payload': payload,
                'reason': str(event.get('reason', 'frontend_command')),
                'operator_id': str(event.get('operator', 'frontend-console')),
            }
        )
        self._node._sync_dispatcher_snapshot()
        self._record_phase(
            event_id,
            event_type,
            'admission',
            admission.status,
            admission.message,
            trace_id=trace_id,
        )
        if not admission.accepted:
            self._node.audit_command(event_id, event_type, admission.status, admission.message)
            self._node.send_ack(event_id, admission.status, admission.message, trace_id=trace_id)

    def dispatch_command(self, cmd: dict[str, Any]) -> None:
        """Dispatch one admitted command into the router path."""
        self._node.record_command_phase(
            str(cmd.get('event_id', 'frontend-event') or 'frontend-event'),
            str(cmd.get('type', 'unknown') or 'unknown'),
            'dispatching',
            'queued',
            'command dispatched to router',
            trace_id=str(cmd.get('trace_id', '') or ''),
        )
        self._node.command_router.handle(cmd)

    def on_dispatch_failure(self, cmd: dict[str, Any], exc: Exception) -> None:
        """Record router-side dispatch failures as stable lifecycle events."""
        self._node.record_command_phase(
            str(cmd.get('event_id', 'frontend-event') or 'frontend-event'),
            str(cmd.get('type', 'unknown') or 'unknown'),
            'dispatch_failed',
            'rejected',
            f'command dispatch failed: {exc}',
            trace_id=str(cmd.get('trace_id', '') or ''),
        )
