from __future__ import annotations

"""System-orchestration registry for lifecycle/readiness/recovery surfaces."""

from dataclasses import dataclass
from typing import Any, Mapping

from robot_contracts.report_surface_registry import report_surface_registry_payload


@dataclass(frozen=True, slots=True)
class RuntimeOrchestrationEntry:
    """Describe one orchestration component surfaced to operators.

    Args:
        component_id: Stable component identifier.
        report_key: Report-surface key exposing the component.
        required_for_mainline: Whether mainline launch semantics require the component.
        runtime_topics: Runtime topics providing the authoritative data.
        operator_visible_fields: Report-detail paths visible to operators.
        truth_source_paths: Canonical implementation/config references.
        recovery_owner: Runtime owner responsible for remediation.
        notes: Supplemental lifecycle/recovery notes.

    Returns:
        Immutable orchestration-registry entry.

    Raises:
        None.
    """

    component_id: str
    report_key: str
    required_for_mainline: bool
    runtime_topics: tuple[str, ...]
    operator_visible_fields: tuple[str, ...]
    truth_source_paths: tuple[str, ...]
    recovery_owner: str
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'componentId': self.component_id,
            'reportKey': self.report_key,
            'requiredForMainline': self.required_for_mainline,
            'runtimeTopics': list(self.runtime_topics),
            'operatorVisibleFields': list(self.operator_visible_fields),
            'truthSourcePaths': list(self.truth_source_paths),
            'recoveryOwner': self.recovery_owner,
            'notes': list(self.notes),
        }


_RUNTIME_ORCHESTRATION_REGISTRY: dict[str, RuntimeOrchestrationEntry] = {
    'startup_barrier': RuntimeOrchestrationEntry(
        component_id='startup_barrier',
        report_key='runtimeSupervision',
        required_for_mainline=True,
        runtime_topics=('/robot/runtime/supervision', '/robot/web_bridge/ready'),
        operator_visible_fields=('startupBarrierReady', 'readiness', 'reasons'),
        truth_source_paths=(
            'ros2_ws/src/robot_bringup/robot_bringup/startup_barrier.py',
            'ros2_ws/src/robot_bringup/robot_bringup/runtime_orchestration_manager.py',
            'ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py',
        ),
        recovery_owner='startup_barrier',
        notes=('Startup barrier readiness is the first operator-visible gate before command entry is considered ready.',),
    ),
    'lifecycle_manager': RuntimeOrchestrationEntry(
        component_id='lifecycle_manager',
        report_key='runtimeSupervision',
        required_for_mainline=False,
        runtime_topics=('/robot/runtime/supervision',),
        operator_visible_fields=(
            'lifecycleManager.present',
            'lifecycleManager.type',
            'lifecycleManager.state',
            'lifecycleManager.managedNodes',
            'lifecycleManager.recentTransitions',
        ),
        truth_source_paths=(
            'ros2_ws/src/robot_bringup/robot_bringup/ros_lifecycle_manager.py',
            'ros2_ws/src/robot_bringup/robot_bringup/runtime_orchestration_manager.py',
            'ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py',
        ),
        recovery_owner='ros_lifecycle_manager',
        notes=('Lifecycle manager state is observability-first and must not be assumed present on every profile.',),
    ),
    'bond_supervision': RuntimeOrchestrationEntry(
        component_id='bond_supervision',
        report_key='runtimeSupervision',
        required_for_mainline=False,
        runtime_topics=('/robot/runtime/supervision',),
        operator_visible_fields=(
            'bondSupervision.present',
            'bondSupervision.type',
            'bondSupervision.state',
            'bondSupervision.managedNodes',
        ),
        truth_source_paths=(
            'ros2_ws/src/robot_bringup/robot_bringup/ros_lifecycle_manager.py',
            'ros2_ws/src/robot_bringup/robot_bringup/runtime_orchestration_manager.py',
            'ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py',
        ),
        recovery_owner='ros_lifecycle_manager',
        notes=('Bond supervision complements lifecycle state and is used to explain degraded recovery conditions.',),
    ),
    'recovery_plan': RuntimeOrchestrationEntry(
        component_id='recovery_plan',
        report_key='runtimeSupervision',
        required_for_mainline=True,
        runtime_topics=('/robot/runtime/supervision',),
        operator_visible_fields=('recoveryMode', 'recoveryPlan.strategy', 'recoveryPlan.reason', 'recoveryPlan.targetNodes'),
        truth_source_paths=(
            'ros2_ws/src/robot_bringup/robot_bringup/runtime_orchestration_manager.py',
            'ros2_ws/src/robot_decision/robot_decision/decision_app_service.py',
            'ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py',
        ),
        recovery_owner='robot_decision',
        notes=('Recovery-plan reporting must stay aligned with runtime supervision and operator-facing safe-stop guidance.',),
    ),
    'operator_surface_readiness': RuntimeOrchestrationEntry(
        component_id='operator_surface_readiness',
        report_key='runtimeSupervision',
        required_for_mainline=True,
        runtime_topics=('/robot/web_bridge/ready', '/robot/runtime/supervision'),
        operator_visible_fields=('startupBarrierReady', 'readiness', 'reasons'),
        truth_source_paths=(
            'robot_frontend/src/bridge/policyKernel.ts',
            'ros2_ws/src/robot_bringup/robot_bringup/runtime_orchestration_manager.py',
            'ros2_ws/src/robot_api_server/robot_api_server/proxy_server.py',
            'ros2_ws/src/robot_web_bridge/robot_web_bridge/web_bridge_node.py',
        ),
        recovery_owner='robot_api_server',
        notes=('Operator-ready status spans API facade readiness, web-bridge readiness, and runtime supervision.',),
    ),
}




def runtime_orchestration_entry(component_id: str) -> RuntimeOrchestrationEntry | None:
    """Return one runtime-orchestration registry entry by component id."""
    return _RUNTIME_ORCHESTRATION_REGISTRY.get(str(component_id or '').strip())


def _path_present(payload: Mapping[str, Any], dotted_path: str) -> bool:
    current: Any = payload
    for segment in str(dotted_path or '').split('.'):
        if not isinstance(current, dict) or segment not in current:
            return False
        current = current.get(segment)
    return True


def runtime_orchestration_runtime_status(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Project runtime supervision payload into registry-keyed component status.

    Returns one mapping keyed by orchestration component id. Each component
    records whether required fields are present so runtime reports can reflect
    missing orchestration surfaces rather than only static registry metadata.
    """
    status: dict[str, dict[str, Any]] = {}
    for component_id, entry in sorted(_RUNTIME_ORCHESTRATION_REGISTRY.items()):
        missing_fields = [field for field in entry.operator_visible_fields if not _path_present(payload, field)]
        status[component_id] = {
            'componentId': component_id,
            'requiredForMainline': bool(entry.required_for_mainline),
            'recoveryOwner': entry.recovery_owner,
            'runtimeTopics': list(entry.runtime_topics),
            'status': 'ready' if not missing_fields else 'missing_fields',
            'missingFields': missing_fields,
        }
    return status


def runtime_orchestration_registry_payload() -> dict[str, dict[str, Any]]:
    """Serialize the runtime-orchestration registry."""
    return {component_id: entry.to_dict() for component_id, entry in sorted(_RUNTIME_ORCHESTRATION_REGISTRY.items())}



def validate_runtime_orchestration_registry() -> list[str]:
    """Validate runtime-orchestration coverage against the report registry.

    Returns:
        List of validation errors. Empty means valid.

    Raises:
        None.
    """
    errors: list[str] = []
    report_registry = report_surface_registry_payload()
    for component_id, entry in sorted(_RUNTIME_ORCHESTRATION_REGISTRY.items()):
        report_entry = report_registry.get(entry.report_key)
        if report_entry is None:
            errors.append(f'{component_id}:missing_report_key:{entry.report_key}')
            continue
        detail_paths = set(str(path) for path in report_entry.get('detailPaths', []))
        for field in entry.operator_visible_fields:
            if field not in detail_paths:
                errors.append(f'{component_id}:missing_visible_field:{field}')
        if not entry.truth_source_paths:
            errors.append(f'{component_id}:missing_truth_source_paths')
        if not entry.runtime_topics:
            errors.append(f'{component_id}:missing_runtime_topics')
    return errors
