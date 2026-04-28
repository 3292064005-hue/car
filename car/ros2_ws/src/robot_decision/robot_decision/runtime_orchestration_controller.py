from __future__ import annotations

"""Decision-side runtime orchestration control-plane helpers.

This module turns runtime-supervision telemetry into one explicit orchestration
state machine used by the decision layer. Unlike the report-surface projection,
it directly influences SAFE_STOP recovery gating and active-mode demotion when
required orchestration components are missing.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from robot_contracts.runtime_orchestration_registry import runtime_orchestration_runtime_status
from robot_utils.constants import MODE_BOOT, MODE_SAFE_STOP

_ACTIVE_MOTION_MODES = {"IDLE", "MANUAL", "PATROL", "TRACK"}


@dataclass(frozen=True, slots=True)
class RuntimeOrchestrationDecision:
    """Result of evaluating one runtime-supervision payload."""

    orchestration_state: str
    blocked_reason: str
    components: dict[str, dict[str, Any]]
    required_missing: tuple[str, ...]
    should_force_safe_stop: bool
    transition_reason: str
    operator_event_name: str
    operator_event_detail: str


class RuntimeOrchestrationController:
    """Evaluate runtime supervision as one control-plane orchestration state machine."""

    def __init__(self, node: Any) -> None:
        self._node = node

    def evaluate(self, payload: Mapping[str, Any]) -> RuntimeOrchestrationDecision:
        if not isinstance(payload, Mapping):
            raise TypeError('runtime supervision payload must be mapping-like')
        raw_components = payload.get('orchestrationComponents')
        if isinstance(raw_components, Mapping):
            components = {
                str(component_id): dict(component_payload) if isinstance(component_payload, Mapping) else {}
                for component_id, component_payload in raw_components.items()
            }
        else:
            components = runtime_orchestration_runtime_status(payload)

        required_missing = tuple(
            component_id
            for component_id, item in sorted(components.items())
            if bool(item.get('requiredForMainline')) and bool(item.get('missingFields'))
        )
        raw_state = str(payload.get('state', '') or '').strip().lower() or 'unknown'
        reasons = payload.get('reasons', [])
        normalized_reasons = [str(item) for item in reasons] if isinstance(reasons, list) else []

        blocked_reason = ''
        orchestration_state = 'ready'
        operator_event_name = 'ready'
        operator_event_detail = 'runtime orchestration ready'

        if raw_state == 'booting':
            orchestration_state = 'booting'
            blocked_reason = 'runtime_orchestration_booting'
            operator_event_name = 'booting'
            operator_event_detail = 'runtime orchestration booting'
        elif required_missing:
            blocked_reason = f"runtime_orchestration_missing_fields:{','.join(required_missing)}"
            orchestration_state = 'blocked' if raw_state in {'faulted', 'unavailable'} else 'recovering'
            operator_event_name = 'required_components_missing'
            operator_event_detail = blocked_reason
        elif raw_state in {'faulted', 'unavailable'}:
            orchestration_state = 'blocked'
            blocked_reason = str(normalized_reasons[0] if normalized_reasons else f'runtime_orchestration_{raw_state}')
            operator_event_name = raw_state
            operator_event_detail = blocked_reason
        elif raw_state == 'degraded':
            orchestration_state = 'degraded'
            blocked_reason = str(normalized_reasons[0] if normalized_reasons else 'runtime_orchestration_degraded')
            operator_event_name = 'degraded'
            operator_event_detail = blocked_reason

        current_mode = str(getattr(self._node, 'current_mode', '') or '').strip().upper()
        should_force_safe_stop = False
        transition_reason = ''
        if current_mode not in {MODE_BOOT, MODE_SAFE_STOP}:
            if orchestration_state == 'blocked':
                should_force_safe_stop = True
                transition_reason = blocked_reason or 'runtime_orchestration_blocked'
            elif orchestration_state == 'recovering' and current_mode in _ACTIVE_MOTION_MODES:
                should_force_safe_stop = True
                transition_reason = blocked_reason or 'runtime_orchestration_recovering'

        return RuntimeOrchestrationDecision(
            orchestration_state=orchestration_state,
            blocked_reason=blocked_reason,
            components=components,
            required_missing=required_missing,
            should_force_safe_stop=should_force_safe_stop,
            transition_reason=transition_reason,
            operator_event_name=operator_event_name,
            operator_event_detail=operator_event_detail,
        )
