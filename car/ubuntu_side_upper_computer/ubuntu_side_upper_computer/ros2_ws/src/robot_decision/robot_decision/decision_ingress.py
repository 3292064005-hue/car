from __future__ import annotations

"""Ingress normalization helpers for the decision runtime.

This module translates ROS-facing request and message payloads into explicit
internal intent payloads. The goal is to keep parsing, defaulting, and input
validation out of ``DecisionNode`` and the state-transition layer.
"""

from dataclasses import dataclass
from typing import Any

from std_msgs.msg import String
from robot_contracts.runtime_param_transport import loads_runtime_param_payload


@dataclass(frozen=True)
class RequestModeChangeIntent:
    """Normalized mode-change request.

    Attributes:
        requested_mode: Target mode string.
        requested_by: Request source label.
        reason: Human-readable transition reason.
        trace_id: Optional correlation identifier.
    """

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


class DecisionIngress:
    """Parse ROS-facing messages into stable internal intent payloads.

    Functions in this class must not mutate node state or publish side effects.
    They are intentionally limited to input coercion and validation.
    """

    def parse_set_mode_request(self, request: Any) -> RequestModeChangeIntent:
        """Parse one ``SetMode`` request.

        Args:
            request: ROS service request object with ``mode``, ``requested_by``,
                ``reason``, and optionally ``trace_id`` fields.

        Returns:
            Normalized mode-change intent.

        Raises:
            TypeError: If the request object is missing required attributes.

        Boundary behavior:
            Empty string fields are preserved as empty strings so that the policy
            layer can enforce business semantics without the parser inventing
            fallback values.
        """
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
        """Parse one ``ResetFault`` request.

        Args:
            request: ROS service request object with ``requested_by``,
                ``reason``, and optionally ``trace_id``.

        Returns:
            Normalized fault-reset intent.

        Raises:
            TypeError: If the request object is missing required attributes.

        Boundary behavior:
            Empty strings remain empty so the decision policy can decide whether
            to reject or audit the request.
        """
        for attr in ('requested_by', 'reason'):
            if not hasattr(request, attr):
                raise TypeError(f'reset-fault request missing attribute: {attr}')
        return ResetFaultIntent(
            requested_by=str(getattr(request, 'requested_by', '') or ''),
            reason=str(getattr(request, 'reason', '') or ''),
            trace_id=str(getattr(request, 'trace_id', '') or ''),
        )

    def parse_fault_msg(self, msg: Any) -> Any:
        """Validate one fault message for downstream policy evaluation.

        Args:
            msg: Fault-like ROS message.

        Returns:
            The original message for downstream processing.

        Raises:
            TypeError: If the message is ``None``.

        Boundary behavior:
            Field-level validation stays intentionally light because the policy
            layer supports partially-populated fault messages.
        """
        if msg is None:
            raise TypeError('fault message must not be None')
        return msg

    def parse_voice_msg(self, msg: Any) -> Any:
        """Validate one voice-command message.

        Args:
            msg: Voice-command message.

        Returns:
            The original message.

        Raises:
            TypeError: If ``msg`` is ``None``.

        Boundary behavior:
            Empty commands are preserved and later treated as ignored commands by
            the policy layer.
        """
        if msg is None:
            raise TypeError('voice command message must not be None')
        return msg

    def parse_target_msg(self, msg: Any) -> Any:
        """Validate one vision target message.

        Args:
            msg: Vision-target message.

        Returns:
            The original message.

        Raises:
            TypeError: If ``msg`` is ``None``.

        Boundary behavior:
            Partial target payloads remain allowed; target-confidence checks are
            deferred to the decision policy.
        """
        if msg is None:
            raise TypeError('vision target message must not be None')
        return msg

    def parse_qrcode_msg(self, msg: String) -> QrcodeIntent:
        """Normalize one QR-code message.

        Args:
            msg: ``std_msgs/String`` payload carrying QR-code data.

        Returns:
            Normalized QR-code intent.

        Raises:
            TypeError: If ``msg`` is ``None``.

        Boundary behavior:
            Empty payloads are preserved as empty strings so callers can treat
            them as no-op observations without reparsing the raw message.
        """
        if msg is None:
            raise TypeError('qrcode message must not be None')
        return QrcodeIntent(data=str(getattr(msg, 'data', '') or ''), raw=msg)

    def parse_runtime_params_msg(self, msg: String) -> RuntimeParamsIntent:
        """Parse one runtime-parameter synchronization message.

        Args:
            msg: ``std_msgs/String`` runtime-parameter payload.

        Returns:
            Parsed runtime-parameter intent containing the raw message and the
            validated transport payload.

        Raises:
            TypeError: If ``msg`` is ``None``.
            RuntimeParamTransportError: If JSON or the transport contract is
                malformed. The concrete exception type is defined by the
                transport helper.

        Boundary behavior:
            The method never mutates the node state. It only validates and
            normalizes the transport payload.
        """
        if msg is None:
            raise TypeError('runtime parameter message must not be None')
        payload = loads_runtime_param_payload(str(getattr(msg, 'data', '') or ''))
        return RuntimeParamsIntent(raw_message=msg, payload=payload)

    def parse_chassis_state_msg(self, msg: Any) -> Any:
        """Validate one chassis-state message.

        Args:
            msg: Chassis-state message.

        Returns:
            The original message.

        Raises:
            TypeError: If ``msg`` is ``None``.
        """
        if msg is None:
            raise TypeError('chassis-state message must not be None')
        return msg

    def parse_system_status_msg(self, msg: Any) -> Any:
        """Validate one system-status message.

        Args:
            msg: System-status message.

        Returns:
            The original message.

        Raises:
            TypeError: If ``msg`` is ``None``.
        """
        if msg is None:
            raise TypeError('system-status message must not be None')
        return msg
