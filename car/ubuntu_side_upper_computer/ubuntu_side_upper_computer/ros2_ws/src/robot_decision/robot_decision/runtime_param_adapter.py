from __future__ import annotations

"""Runtime-parameter application helpers for the decision runtime."""

from dataclasses import dataclass
from typing import Any

from std_msgs.msg import String

from robot_contracts.runtime_param_transport import (
    build_runtime_param_apply_result,
    loads_runtime_param_payload,
)
from robot_utils.error_policy import classify_exception, publish_policy_outcome


@dataclass(frozen=True)
class RuntimeParamApplyOutcome:
    """Result of applying one runtime-parameter payload.

    Attributes:
        params: Effective runtime-parameter dictionary.
        apply_result_payload: Bridge-facing apply-result payload.
        ok: Whether parsing and application succeeded.
    """

    params: dict[str, Any]
    apply_result_payload: dict[str, Any]
    ok: bool


class RuntimeParamAdapter:
    """Apply bridge-published runtime parameters to the decision layer.

    The adapter keeps runtime-parameter parsing and fallback semantics out of the
    ROS node composition root. Publishing of apply-result telemetry is delegated
    to ``DecisionSideEffects`` so the adapter remains side-effect free.
    """

    def __init__(self, node: Any) -> None:
        self._node = node

    def runtime_param_value(self, key: str, fallback: float) -> float:
        """Resolve one runtime parameter with a numeric fallback.

        Args:
            key: Runtime parameter key.
            fallback: Fallback value used when the override is missing or invalid.

        Returns:
            Effective numeric value.

        Raises:
            None.

        Boundary behavior:
            Invalid override values are ignored and replaced by the numeric
            fallback. This guarantees deterministic control limits.
        """
        raw = self._node._runtime_param_overrides.get(key, fallback)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(fallback)

    def apply_message(self, msg: String) -> RuntimeParamApplyOutcome:
        """Parse one runtime-parameter message and build the apply outcome.

        Args:
            msg: ``std_msgs/String`` runtime-parameter payload.

        Returns:
            Structured apply outcome.

        Raises:
            None. All parsing failures are converted into policy outcomes and a
            negative apply-result payload.
        """
        try:
            payload = loads_runtime_param_payload(str(getattr(msg, 'data', '') or ''))
        except Exception as exc:
            return self._build_error_outcome(
                transaction_id='',
                runtime_param_version=0,
                ts='',
                trace_id='',
                exc=exc,
            )
        return self.apply_payload(payload)

    def apply_payload(self, payload: dict[str, Any]) -> RuntimeParamApplyOutcome:
        """Validate one parsed runtime-parameter payload.

        Args:
            payload: Parsed runtime-parameter transport payload.

        Returns:
            Structured apply outcome.

        Raises:
            None. Invalid ``params`` values are converted into explicit failure
            outcomes instead of bubbling exceptions into callback threads.
        """
        params = payload.get('params', {})
        if not isinstance(params, dict):
            return self._build_error_outcome(
                transaction_id=str(payload.get('transaction_id', '') or ''),
                runtime_param_version=int(payload.get('runtime_param_version', 0) or 0),
                ts=str(payload.get('ts', '') or ''),
                trace_id=str(payload.get('trace_id', '') or ''),
                exc=TypeError('params must be an object'),
            )
        normalized_params = dict(params)
        return RuntimeParamApplyOutcome(
            params=normalized_params,
            apply_result_payload=build_runtime_param_apply_result(
                consumer='robot_decision',
                transaction_id=str(payload.get('transaction_id', '') or ''),
                runtime_param_version=int(payload.get('runtime_param_version', 0) or 0),
                ok=True,
                message='decision runtime parameters applied',
                ts=str(payload.get('ts', '') or ''),
                trace_id=str(payload.get('trace_id', '') or ''),
            ),
            ok=True,
        )

    def _build_error_outcome(
        self,
        *,
        transaction_id: str,
        runtime_param_version: int,
        ts: str,
        trace_id: str,
        exc: Exception,
    ) -> RuntimeParamApplyOutcome:
        publish_policy_outcome(
            self._node,
            outcome=classify_exception(
                'decision.runtime_params',
                exc,
                code='DECISION_RUNTIME_PARAMS_INVALID',
                operator_message='decision runtime parameter sync failed',
            ),
            event_pub=getattr(self._node, 'event_pub', None),
        )
        message = f'decision runtime parameter sync failed: {exc}'
        return RuntimeParamApplyOutcome(
            params={},
            apply_result_payload=build_runtime_param_apply_result(
                consumer='robot_decision',
                transaction_id=transaction_id,
                runtime_param_version=runtime_param_version,
                ok=False,
                message=message,
                ts=ts,
                trace_id=trace_id,
            ),
            ok=False,
        )
