from __future__ import annotations

"""Mission-stage admission and execution helpers.

The task graph is product-visible, so every exported stage kind must have an
explicit runtime owner and completion rule. Unsupported kinds are rejected at
mission-admission time instead of being silently auto-completed.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StageAdmission:
    kind: str
    supported: bool
    owner: str
    start_condition: str
    completion_condition: str
    timeout_sec: float
    reason: str = ''

    def to_dict(self) -> dict[str, object]:
        return {
            'kind': self.kind,
            'supported': self.supported,
            'owner': self.owner,
            'startCondition': self.start_condition,
            'completionCondition': self.completion_condition,
            'timeoutSec': round(self.timeout_sec, 3),
            'reason': self.reason or None,
        }


@dataclass(frozen=True)
class StageExecutionResult:
    status: str
    reason: str
    navigation_route_name: str = ''


class StageExecutor:
    kind = 'unsupported'

    def admit(self, stage: dict[str, Any]) -> StageAdmission:
        raise NotImplementedError

    def start(self, node: Any, stage: dict[str, Any], *, current_stage_completed: bool) -> StageExecutionResult:
        raise NotImplementedError


class RouteStageExecutor(StageExecutor):
    kind = 'route'

    def admit(self, stage: dict[str, Any]) -> StageAdmission:
        route_name = str(stage.get('routeName', '') or '').strip()
        if not route_name:
            return StageAdmission(self.kind, False, 'robot_navigation', 'route_request_available', 'route_completed', 0.0, 'route_stage_missing_route_name')
        return StageAdmission(self.kind, True, 'robot_navigation', 'mission_entered_or_previous_stage_completed', 'navigation_state=route_completed', max(0.0, float(stage.get('timeoutSec', 0.0) or 0.0)))

    def start(self, node: Any, stage: dict[str, Any], *, current_stage_completed: bool) -> StageExecutionResult:
        route_name = str(stage.get('routeName', '') or '').strip()
        if not route_name:
            return StageExecutionResult('failed', 'route_stage_missing_route_name')
        node.context.navigation_state = 'route_requested'
        node.context.navigation_route_name = route_name
        node.context.navigation_goal_id = ''
        node.context.navigation_goal_label = ''
        node.context.navigation_completed_goals = 0
        node.context.navigation_total_goals = 0
        node.context.navigation_progress = 0.0
        node.context.navigation_reason = f'stage_start:{node.context.current_task_stage_id or route_name}'
        return StageExecutionResult('started', node.context.navigation_reason, navigation_route_name=route_name)


class VerificationStageExecutor(StageExecutor):
    kind = 'verification'

    def admit(self, stage: dict[str, Any]) -> StageAdmission:
        verification_rules = stage.get('verificationRules', {})
        if verification_rules is not None and not isinstance(verification_rules, dict):
            return StageAdmission(self.kind, False, 'robot_decision', 'previous_stage_completed', 'verification_rules_satisfied', 0.0, 'verification_rules_must_be_mapping')
        return StageAdmission(
            self.kind,
            True,
            'robot_decision',
            'previous_stage_completed',
            'navigation_completion_and_runtime_health_verified',
            max(0.0, float(stage.get('timeoutSec', 0.0) or 0.0)),
        )

    def start(self, node: Any, stage: dict[str, Any], *, current_stage_completed: bool) -> StageExecutionResult:
        if not current_stage_completed:
            return StageExecutionResult('failed', 'verification_requires_previous_stage_completion')
        rules = stage.get('verificationRules', {})
        if not isinstance(rules, dict):
            rules = {}
        required_navigation_state = str(rules.get('requiredNavigationState', 'route_completed') or 'route_completed')
        minimum_completed_goals = max(0, int(rules.get('minimumCompletedGoals', 1) or 1))
        require_positive_progress = bool(rules.get('requirePositiveProgress', True))
        require_runtime_ready = bool(rules.get('requireRuntimeReady', True))

        navigation_state = str(getattr(node.context, 'navigation_state', '') or '')
        completed_goals = int(getattr(node.context, 'navigation_completed_goals', 0) or 0)
        progress = float(getattr(node.context, 'navigation_progress', 0.0) or 0.0)
        runtime_state = str(getattr(node.context, 'runtime_supervision_state', '') or '')

        if navigation_state != required_navigation_state:
            return StageExecutionResult('failed', f'verification_failed:navigation_state={navigation_state or "missing"}')
        if completed_goals < minimum_completed_goals:
            return StageExecutionResult('failed', f'verification_failed:completed_goals<{minimum_completed_goals}')
        if require_positive_progress and progress < 1.0:
            return StageExecutionResult('failed', f'verification_failed:progress={progress:.3f}')
        if require_runtime_ready and runtime_state not in {'ready', 'degraded'}:
            return StageExecutionResult('failed', f'verification_failed:runtime_supervision={runtime_state or "missing"}')
        return StageExecutionResult('completed', str(stage.get('successMessage', '') or 'verification_complete'))


_EXECUTORS: dict[str, StageExecutor] = {
    'route': RouteStageExecutor(),
    'verification': VerificationStageExecutor(),
}


def supported_stage_kinds() -> tuple[str, ...]:
    return tuple(sorted(_EXECUTORS))


def stage_executor(kind: str) -> StageExecutor | None:
    return _EXECUTORS.get(str(kind or '').strip().lower())


def admit_stage(stage: dict[str, Any]) -> StageAdmission:
    executor = stage_executor(str(stage.get('kind', 'route') or 'route'))
    if executor is None:
        kind = str(stage.get('kind', 'route') or 'route')
        return StageAdmission(kind, False, 'unassigned', 'unsupported', 'unsupported', 0.0, f'unsupported_stage_kind:{kind}')
    return executor.admit(stage)


def admit_stage_payload(stage: dict[str, Any]) -> dict[str, object]:
    admission = admit_stage(stage)
    payload = dict(stage)
    payload.update(admission.to_dict())
    return payload


def start_stage(node: Any, stage: dict[str, Any], *, current_stage_completed: bool) -> StageExecutionResult:
    executor = stage_executor(str(stage.get('kind', 'route') or 'route'))
    if executor is None:
        return StageExecutionResult('failed', f'unsupported_stage_kind:{stage.get("kind", "route")}')
    return executor.start(node, stage, current_stage_completed=current_stage_completed)
