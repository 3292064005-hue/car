from __future__ import annotations

"""Contract for future multi-robot / scheduler integration."""

from pathlib import Path
from typing import Any

import yaml

SUPPORTED_FLEET_ADAPTER_FAMILIES = ('disabled', 'open_rmf', 'free_fleet', 'custom_scheduler')


def load_fleet_adapter_boundary_params(config_root: str | Path | None) -> dict[str, Any]:
    root = Path(str(config_root or '').strip()) if config_root else None
    source = root / 'fleet_adapter.yaml' if root else None
    if source is None or not source.is_file():
        return {}
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    config = payload.get('robot_fleet_adapter_boundary', payload) if isinstance(payload, dict) else {}
    params = config.get('ros__parameters', {}) if isinstance(config, dict) and isinstance(config.get('ros__parameters', {}), dict) else {}
    return {
        'enabled': bool(params.get('fleet_adapter_enabled', False)),
        'adapter_family': str(params.get('fleet_adapter_family', 'disabled') or 'disabled').strip() or 'disabled',
        'task_ingress_topic': str(params.get('fleet_task_ingress_topic', '/robot/fleet_adapter/tasks') or '/robot/fleet_adapter/tasks').strip() or '/robot/fleet_adapter/tasks',
        'status_topic': str(params.get('fleet_status_topic', '/robot/fleet_adapter/status') or '/robot/fleet_adapter/status').strip() or '/robot/fleet_adapter/status',
        'accepted_task_kinds': tuple(str(item).strip() for item in params.get('fleet_accepted_task_kinds', ['patrol_route']) if str(item).strip()),
    }


def fleet_adapter_boundary_contract(*, enabled: bool = False, adapter_family: str = 'disabled', task_ingress_topic: str = '/robot/fleet_adapter/tasks', status_topic: str = '/robot/fleet_adapter/status', accepted_task_kinds: tuple[str, ...] = ('patrol_route',)) -> dict[str, Any]:
    """Resolve the fleet-adapter boundary under a single-robot-only policy.

    Args:
        enabled: Requested external scheduler enable flag from config.
        adapter_family: Requested external adapter family identifier.
        task_ingress_topic: Read-only ingress topic reserved for future adapters.
        status_topic: Read-only status topic reserved for future adapters.
        accepted_task_kinds: Future task kinds accepted at the boundary.

    Returns:
        Serializable boundary contract that explicitly rejects runtime activation
        while keeping the single-robot ingress contract stable.

    Raises:
        None. Unsupported adapter families are normalized to ``custom_scheduler``.
    """
    normalized_family = str(adapter_family or 'disabled').strip() or 'disabled'
    if normalized_family not in SUPPORTED_FLEET_ADAPTER_FAMILIES:
        normalized_family = 'custom_scheduler'
    requested_enabled = bool(enabled and normalized_family != 'disabled')
    activation_decision = 'reject' if requested_enabled else 'disabled'
    status = 'single_robot_only_runtime_rejects_external_scheduler_activation' if requested_enabled else 'disabled_by_default'
    policy_reason = 'single_robot_only_product_policy' if requested_enabled else 'disabled_by_default'
    return {
        'contractVersion': '1.1.0',
        'status': status,
        'enabled': False,
        'requestedEnabled': requested_enabled,
        'activationDecision': activation_decision,
        'policyReason': policy_reason,
        'adapterFamily': normalized_family,
        'singleRobotAuthority': True,
        'singleRobotAuthorityOwners': ['robot_decision', 'robot_navigation'],
        'taskIngressTopic': str(task_ingress_topic),
        'statusTopic': str(status_topic),
        'acceptedTaskKinds': list(accepted_task_kinds),
        'authorityBoundary': 'decision_runtime_authoritative',
        'notes': [
            '当前产品发布面固定为单机任务编排。',
            '任何外部 scheduler/fleet manager 都不得在当前版本激活运行时接入。',
            '未来若恢复车队调度，只能通过 fleet adapter boundary 进入 decision task layer。',
        ],
    }


def resolve_fleet_adapter_boundary_contract(config_root: str | Path | None) -> dict[str, Any]:
    params = load_fleet_adapter_boundary_params(config_root)
    return fleet_adapter_boundary_contract(enabled=bool(params.get('enabled', False)), adapter_family=str(params.get('adapter_family', 'disabled') or 'disabled'), task_ingress_topic=str(params.get('task_ingress_topic', '/robot/fleet_adapter/tasks') or '/robot/fleet_adapter/tasks'), status_topic=str(params.get('status_topic', '/robot/fleet_adapter/status') or '/robot/fleet_adapter/status'), accepted_task_kinds=tuple(params.get('accepted_task_kinds', ('patrol_route',))))
