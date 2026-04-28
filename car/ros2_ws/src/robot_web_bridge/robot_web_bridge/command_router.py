from __future__ import annotations

from typing import Any, Mapping
import math
import time

from robot_contracts.bridge_contract import command_allowed_modes
from robot_contracts.command_route_registry import command_route_handler_name
from robot_utils.action_support import load_robot_actions
from .components.command_handlers import CommandHandlers
from .components.command_application_service import CommandApplicationService
from .components import command_runtime_surface as command_runtime
try:
    from rclpy.action import ActionClient
except Exception:  # pragma: no cover - lightweight test/runtime envs may omit actions
    ActionClient = None

from .components.command_execution_service import (
    ActionBinding,
    CommandExecutionService,
    PendingAck,
    PendingTimeout,
    DEFAULT_COMMAND_FUTURE_TIMEOUT_SEC,
)


def _coerce_float_field(payload: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key not in payload:
            continue
        raw = payload.get(key)
        if raw in (None, ''):
            return float(default)
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'invalid numeric field {key}: {raw!r}') from exc
        if not math.isfinite(value):
            raise ValueError(f'invalid numeric field {key}: {raw!r}')
        return value
    return float(default)


def _coerce_int_field(payload: Mapping[str, Any], key: str, *, default: int) -> int:
    raw = payload.get(key)
    if raw in (None, ''):
        return int(default)
    if isinstance(raw, bool):
        raise ValueError(f'invalid integer field {key}: {raw!r}')
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'invalid integer field {key}: {raw!r}') from exc



def command_allowed_for_mode(command_type: str, current_mode: str) -> bool:
    allowed = command_allowed_modes(command_type)
    return not allowed or current_mode in allowed



def permission_denial_reason(command_type: str, current_mode: str) -> str:
    allowed = command_allowed_modes(command_type)
    if not allowed:
        return f'unsupported command: {command_type}'
    return f'{command_type} is not allowed while mode={current_mode}; allowed modes: {", ".join(allowed)}'


class CommandRouter:
    """Transport-facing router that delegates execution state to dedicated services.

    The router keeps transport/runtime-surface helpers and the authoritative
    command application boundary. Pending ACK bookkeeping, timeout enforcement,
    and action/service completion handling live in
    :class:`CommandExecutionService` so command orchestration does not accumulate
    execution-state responsibilities.
    """

    _coerce_float_field = staticmethod(_coerce_float_field)
    _coerce_int_field = staticmethod(_coerce_int_field)

    def __init__(
        self,
        node: Any,
        *,
        operation_timeout_sec: float = DEFAULT_COMMAND_FUTURE_TIMEOUT_SEC,
        monotonic: Any | None = None,
    ) -> None:
        self.node = node
        self._operation_timeout_sec = float(operation_timeout_sec) if float(operation_timeout_sec) > 0.0 else DEFAULT_COMMAND_FUTURE_TIMEOUT_SEC
        self._monotonic = monotonic or time.monotonic
        self._execution = CommandExecutionService(self, operation_timeout_sec=self._operation_timeout_sec, monotonic=self._monotonic, action_client_factory=ActionClient, action_loader=load_robot_actions)
        self._command_handlers = CommandHandlers(self)
        self._handlers = self._command_handlers.build_registry()
        for command_type, handler in sorted(self._handlers.items()):
            expected_handler = command_route_handler_name(command_type)
            actual_handler = getattr(handler, '__name__', '')
            if expected_handler and actual_handler and expected_handler != actual_handler:
                raise RuntimeError(f'command handler mismatch for {command_type}: expected {expected_handler}, got {actual_handler}')
        self._command_application = CommandApplicationService(self, self._handlers)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._execution, name)

    def _audit(self, event_id: str, command_type: str, status: str, message: str) -> None:
        command_runtime.audit(self, event_id, command_type, status, message)

    def _record_phase(self, event_id: str, command_type: str, phase: str, status: str, message: str, *, trace_id: str = '', extra: Mapping[str, Any] | None = None) -> None:
        command_runtime.record_phase(self, event_id, command_type, phase, status, message, trace_id=trace_id, extra=extra)

    def _send_ack(self, event_id: str, command_type: str, lifecycle_status: str, message: str, *, trace_id: str = '', detail: str = '', lifecycle_phase: str = '') -> None:
        command_runtime.send_ack(self, event_id, command_type, lifecycle_status, message, trace_id=trace_id, detail=detail, lifecycle_phase=lifecycle_phase)

    def _update_task_state(self, payload: Mapping[str, Any]) -> None:
        command_runtime.update_task_state(self, payload)

    def _deny(self, event_id: str, command_type: str, message: str, *, trace_id: str = '', detail: str = '', source_surface: str = '') -> None:
        command_runtime.deny(self, event_id, command_type, message, trace_id=trace_id, detail=detail, source_surface=source_surface)

    def _reject(self, event_id: str, command_type: str, message: str, *, trace_id: str = '', detail: str = '', source_surface: str = '') -> None:
        command_runtime.reject(self, event_id, command_type, message, trace_id=trace_id, detail=detail, source_surface=source_surface)

    def _wait_for_service(self, client: Any, *, name: str) -> bool:
        return command_runtime.wait_for_service(self, client, name=name)

    def _wait_for_action_server(self, client: Any, *, name: str) -> bool:
        return command_runtime.wait_for_action_server(self, client, name=name)

    def handle(self, cmd: dict[str, Any]) -> None:
        """Route one transport-level command through the authoritative application layer."""
        self._command_application.dispatch(cmd)
