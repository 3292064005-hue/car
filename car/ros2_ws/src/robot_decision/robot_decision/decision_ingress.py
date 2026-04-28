from __future__ import annotations

"""Ingress normalization helpers for the decision runtime.

This module translates ROS-facing request and message payloads into explicit
internal intent payloads. The goal is to keep parsing, defaulting, and input
validation out of ``DecisionNode`` and the state-transition layer.
"""

from dataclasses import dataclass
import json
from typing import Any

from std_msgs.msg import String
from robot_contracts.runtime_param_transport import loads_runtime_param_payload


@dataclass(frozen=True)
class RequestModeChangeIntent:
    """Normalized mode-change request."""

    requested_mode: str
    requested_by: str
    reason: str
    trace_id: str = ''


@dataclass(frozen=True)
class ResetFaultIntent:
    """Normalized fault-reset request."""

    requested_by: str
    reason: str
    trace_id: str = ''


@dataclass(frozen=True)
class QrcodeIntent:
    """Normalized QR-code observation."""

    data: str
    raw: Any


@dataclass(frozen=True)
class RuntimeParamsIntent:
    """Normalized runtime-parameter synchronization payload."""

    raw_message: String
    payload: dict[str, Any]


@dataclass(frozen=True)
class NavigationStatusIntent:
    """Normalized navigation status report."""

    raw_message: String
    payload: dict[str, Any]


@dataclass(frozen=True)
class RuntimeOrchestrationIntent:
    """Normalized runtime-orchestration report."""

    raw_message: String
    payload: dict[str, Any]


@dataclass(frozen=True)
class RuntimeSupervisionIntent:
    """Normalized runtime-supervision report."""

    raw_message: String
    payload: dict[str, Any]


class DecisionIngress:
    """Parse ROS-facing messages into stable internal intent payloads."""

    def parse_set_mode_request(self, request: Any) -> RequestModeChangeIntent:
        for attr in ('mode', 'requested_by', 'reason'):
            if not hasattr(request, attr):
                raise TypeError(f'set-mode request missing attribute: {attr}')
        return RequestModeChangeIntent(
            requested_mode=str(getattr(request, 'mode', '') or ''),
            requested_by=str(getattr(request, 'requested_by', '') or ''),
            reason=str(getattr(request, 'reason', '') or ''),
            trace_id=str(getattr(request, 'trace_id', '') or ''),
        )

    def parse_reset_fault_request(self, request: Any) -> ResetFaultIntent:
        for attr in ('requested_by', 'reason'):
            if not hasattr(request, attr):
                raise TypeError(f'reset-fault request missing attribute: {attr}')
        return ResetFaultIntent(
            requested_by=str(getattr(request, 'requested_by', '') or ''),
            reason=str(getattr(request, 'reason', '') or ''),
            trace_id=str(getattr(request, 'trace_id', '') or ''),
        )

    def parse_fault_msg(self, msg: Any) -> Any:
        if msg is None:
            raise TypeError('fault message must not be None')
        return msg

    def parse_voice_msg(self, msg: Any) -> Any:
        if msg is None:
            raise TypeError('voice command message must not be None')
        return msg

    def parse_target_msg(self, msg: Any) -> Any:
        if msg is None:
            raise TypeError('vision target message must not be None')
        return msg

    def parse_qrcode_msg(self, msg: String) -> QrcodeIntent:
        if msg is None:
            raise TypeError('qrcode message must not be None')
        return QrcodeIntent(data=str(getattr(msg, 'data', '') or ''), raw=msg)

    def parse_runtime_params_msg(self, msg: String) -> RuntimeParamsIntent:
        if msg is None:
            raise TypeError('runtime parameter message must not be None')
        payload = loads_runtime_param_payload(str(getattr(msg, 'data', '') or ''))
        return RuntimeParamsIntent(raw_message=msg, payload=payload)

    def parse_navigation_status_msg(self, msg: String) -> NavigationStatusIntent:
        """Parse one navigation status JSON payload.

        Args:
            msg: ``std_msgs/String`` JSON status emitted by ``robot_navigation``.

        Returns:
            Parsed navigation status payload.

        Raises:
            TypeError: If the input message is ``None``.
            ValueError: If the message payload is not a JSON object.
        """
        if msg is None:
            raise TypeError('navigation status message must not be None')
        payload = json.loads(str(getattr(msg, 'data', '') or '{}'))
        if not isinstance(payload, dict):
            raise ValueError('navigation status payload must be a JSON object')
        return NavigationStatusIntent(raw_message=msg, payload=payload)

    def parse_runtime_supervision_msg(self, msg: String) -> RuntimeSupervisionIntent:
        """Parse one runtime supervision JSON payload."""
        if msg is None:
            raise TypeError('runtime supervision message must not be None')
        payload = json.loads(str(getattr(msg, 'data', '') or '{}'))
        if not isinstance(payload, dict):
            raise ValueError('runtime supervision payload must be a JSON object')
        return RuntimeSupervisionIntent(raw_message=msg, payload=payload)

    def parse_runtime_orchestration_msg(self, msg: String) -> RuntimeOrchestrationIntent:
        """Parse one runtime orchestration JSON payload."""
        if msg is None:
            raise TypeError('runtime orchestration message must not be None')
        payload = json.loads(str(getattr(msg, 'data', '') or '{}'))
        if not isinstance(payload, dict):
            raise ValueError('runtime orchestration payload must be a JSON object')
        return RuntimeOrchestrationIntent(raw_message=msg, payload=payload)

    def parse_chassis_state_msg(self, msg: Any) -> Any:
        if msg is None:
            raise TypeError('chassis-state message must not be None')
        return msg

    def parse_system_status_msg(self, msg: Any) -> Any:
        if msg is None:
            raise TypeError('system-status message must not be None')
        return msg
