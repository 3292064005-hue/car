from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from robot_utils.constants import FAULT_LEVEL_ERROR, FAULT_LEVEL_FATAL
from robot_utils.message_factory import make_event, make_fault

ERROR_STARTUP_FAILED = 'startup_failed'
ERROR_DEGRADED = 'degraded'
ERROR_SAFE_STOP = 'safe_stop'
ERROR_FAULT_LATCHED = 'fault_latched'
ERROR_IGNORE_WITH_METRIC = 'ignore_with_metric'


@dataclass(frozen=True)
class PolicyOutcome:
    """Normalized fault/error policy result for all runtime modules.

    Attributes:
        code: Stable machine-readable error code.
        source: Module/source emitting the outcome.
        disposition: One of the ``ERROR_*`` constants.
        event_name: Event-log name emitted for operators.
        event_level: Event-log severity.
        operator_message: Human-readable message for logs/UIs.
        recoverable: Whether the fault can recover automatically or by operator action.
        fault_level: Optional fault severity when a Fault message should be emitted.
        evidence_reference: Short evidence/ref string, usually ``ExceptionType:message``.
        exception_type: Exception class name, if any.
        exception_message: Exception string, if any.
    """

    code: str
    source: str
    disposition: str
    event_name: str
    event_level: str
    operator_message: str
    recoverable: bool = True
    fault_level: str | None = None
    evidence_reference: str = ''
    exception_type: str = ''
    exception_message: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_policy_outcome(
    *,
    code: str,
    source: str,
    disposition: str,
    operator_message: str,
    event_name: str | None = None,
    event_level: str = 'warn',
    recoverable: bool = True,
    fault_level: str | None = None,
    evidence_reference: str = '',
    exception: BaseException | None = None,
) -> PolicyOutcome:
    """Construct one normalized policy outcome."""
    exception_type = type(exception).__name__ if exception is not None else ''
    exception_message = str(exception) if exception is not None else ''
    evidence = evidence_reference or (f'{exception_type}:{exception_message}' if exception_type else '')
    return PolicyOutcome(
        code=code,
        source=source,
        disposition=disposition,
        event_name=event_name or code.lower(),
        event_level=event_level,
        operator_message=operator_message,
        recoverable=recoverable,
        fault_level=fault_level,
        evidence_reference=evidence,
        exception_type=exception_type,
        exception_message=exception_message,
    )


def classify_exception(
    source: str,
    exc: BaseException,
    *,
    code: str | None = None,
    operator_message: str | None = None,
) -> PolicyOutcome:
    """Map one exception to a normalized policy outcome.

    The mapping intentionally centralizes runtime semantics so that config failures,
    malformed payloads and transport issues land on a consistent disposition family.
    """
    from robot_utils.config_loader import ConfigValidationError, StructuredConfigLoadError

    if isinstance(exc, StructuredConfigLoadError):
        return build_policy_outcome(
            code=code or 'CONFIG_LOAD_FAILED',
            source=source,
            disposition=ERROR_STARTUP_FAILED,
            operator_message=operator_message or str(exc),
            event_name='startup_failed',
            event_level='error',
            recoverable=False,
            fault_level=FAULT_LEVEL_FATAL,
            exception=exc,
        )
    if isinstance(exc, ConfigValidationError):
        return build_policy_outcome(
            code=code or 'CONFIG_VALIDATION_FAILED',
            source=source,
            disposition=ERROR_STARTUP_FAILED,
            operator_message=operator_message or str(exc),
            event_name='config_invalid',
            event_level='error',
            recoverable=False,
            fault_level=FAULT_LEVEL_ERROR,
            exception=exc,
        )
    if isinstance(exc, TimeoutError):
        return build_policy_outcome(
            code=code or 'IO_TIMEOUT',
            source=source,
            disposition=ERROR_DEGRADED,
            operator_message=operator_message or str(exc) or 'I/O timeout',
            event_name='io_timeout',
            event_level='warn',
            recoverable=True,
            fault_level=FAULT_LEVEL_ERROR,
            exception=exc,
        )
    if isinstance(exc, (ConnectionError, OSError)):
        return build_policy_outcome(
            code=code or 'IO_DEGRADED',
            source=source,
            disposition=ERROR_DEGRADED,
            operator_message=operator_message or str(exc) or 'transport degraded',
            event_name='io_degraded',
            event_level='warn',
            recoverable=True,
            fault_level=FAULT_LEVEL_ERROR,
            exception=exc,
        )
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return build_policy_outcome(
            code=code or 'INVALID_INPUT',
            source=source,
            disposition=ERROR_IGNORE_WITH_METRIC,
            operator_message=operator_message or str(exc) or 'invalid input',
            event_name='invalid_input',
            event_level='warn',
            recoverable=True,
            fault_level=None,
            exception=exc,
        )
    return build_policy_outcome(
        code=code or 'UNEXPECTED_RUNTIME_ERROR',
        source=source,
        disposition=ERROR_DEGRADED,
        operator_message=operator_message or str(exc) or 'unexpected runtime error',
        event_name='runtime_error',
        event_level='error',
        recoverable=True,
        fault_level=FAULT_LEVEL_ERROR,
        exception=exc,
    )


def publish_policy_outcome(
    node: Any,
    *,
    outcome: PolicyOutcome,
    event_pub: Any | None = None,
    fault_pub: Any | None = None,
    fault_source: str | None = None,
) -> PolicyOutcome:
    """Emit a normalized policy outcome through event/fault/log channels.

    Args:
        node: ROS node or logger owner with ``get_logger`` and ``get_clock`` methods.
        outcome: Normalized policy outcome to emit.
        event_pub: Optional ``EventLog`` publisher.
        fault_pub: Optional ``Fault`` publisher.
        fault_source: Optional fault source override.

    Returns:
        The same ``PolicyOutcome`` for fluent call sites.
    """
    logger = node.get_logger() if node is not None else None
    detail = outcome.operator_message
    if outcome.evidence_reference:
        detail = f'{detail} | evidence={outcome.evidence_reference}'
    if event_pub is not None:
        event_pub.publish(make_event(node, outcome.source, outcome.event_name, detail, level=outcome.event_level))
    if fault_pub is not None and outcome.fault_level is not None:
        fault_pub.publish(
            make_fault(
                node,
                outcome.code,
                outcome.fault_level,
                fault_source or outcome.source,
                outcome.operator_message,
                recoverable=outcome.recoverable,
            )
        )
    if logger is not None:
        log_line = f'[{outcome.disposition}] {outcome.code}: {detail}'
        if outcome.event_level in {'error', 'critical'}:
            logger.error(log_line)
        elif outcome.event_level in {'warn', 'warning'}:
            logger.warning(log_line)
        else:
            logger.info(log_line)
    return outcome
