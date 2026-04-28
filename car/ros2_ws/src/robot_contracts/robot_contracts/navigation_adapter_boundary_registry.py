from __future__ import annotations

"""Navigation adapter-boundary registry.

This registry keeps the mainline provider and the governed Nav2 adapter lane in a
single declarative table so reports/docs can describe promotion, rollback, and
non-claim boundaries without scattering those facts across launch code,
capability entries, and release notes.
"""

from dataclasses import dataclass
from typing import Any

from robot_contracts.capability_registry import get_capability_entry
from robot_contracts.lane_registry import get_lane_entry


@dataclass(frozen=True, slots=True)
class NavigationAdapterBoundaryEntry:
    """Describe one navigation lane's adapter-boundary contract."""

    lane_id: str
    provider_name: str
    boundary_role: str
    package_name: str
    executable: str
    adapter_runtime: bool
    default_mainline: bool
    promotion_checklist: tuple[str, ...]
    rollback_baseline: str
    non_claims: tuple[str, ...]
    truth_source_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'laneId': self.lane_id,
            'providerName': self.provider_name,
            'boundaryRole': self.boundary_role,
            'packageName': self.package_name,
            'executable': self.executable,
            'adapterRuntime': self.adapter_runtime,
            'defaultMainline': self.default_mainline,
            'promotionChecklist': list(self.promotion_checklist),
            'rollbackBaseline': self.rollback_baseline,
            'nonClaims': list(self.non_claims),
            'truthSourcePaths': list(self.truth_source_paths),
        }


_REGISTRY: dict[str, NavigationAdapterBoundaryEntry] = {
    'simple_nav_provider': NavigationAdapterBoundaryEntry(
        lane_id='navigation.simple_nav_provider',
        provider_name='simple_nav_provider',
        boundary_role='mainline_provider',
        package_name='robot_navigation',
        executable='navigation_node',
        adapter_runtime=False,
        default_mainline=True,
        promotion_checklist=('host_harness_smoke',),
        rollback_baseline='self',
        non_claims=('does_not_claim_external_nav2_stack',),
        truth_source_paths=(
            'ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py',
            'ros2_ws/src/robot_navigation/robot_navigation/navigation_node.py',
        ),
    ),
    'nav2_provider': NavigationAdapterBoundaryEntry(
        lane_id='navigation.nav2_provider',
        provider_name='nav2_provider',
        boundary_role='governed_adapter_boundary',
        package_name='robot_nav2_adapter',
        executable='nav2_adapter_node',
        adapter_runtime=True,
        default_mainline=False,
        promotion_checklist=(
            'simulation_smoke',
            'host_harness_smoke',
            'provider_switch_smoke',
            'operator_docs_review',
            'target_environment_acceptance',
            'external_backend_smoke',
        ),
        rollback_baseline='simple_nav_provider',
        non_claims=(
            'does_not_claim_external_nav2_backend_integration_when_running_local_adapter',
            'does_not_claim_nav2_planner_controller_recovery_servers_present_without_backend_integration',
        ),
        truth_source_paths=(
            'ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py',
            'ros2_ws/src/robot_nav2_adapter/robot_nav2_adapter/backend_claims.py',
            'ros2_ws/src/robot_nav2_adapter/robot_nav2_adapter/nav2_adapter_node.py',
        ),
    ),
}


def navigation_adapter_boundary_entry(provider_name: str) -> NavigationAdapterBoundaryEntry | None:
    """Return one navigation adapter-boundary entry by provider name."""
    return _REGISTRY.get(str(provider_name or '').strip())


def navigation_adapter_boundary_registry_payload() -> dict[str, dict[str, Any]]:
    return {provider: entry.to_dict() for provider, entry in sorted(_REGISTRY.items())}



def validate_navigation_adapter_boundary_registry() -> list[str]:
    errors: list[str] = []
    for provider, entry in sorted(_REGISTRY.items()):
        lane = get_lane_entry(entry.lane_id).to_dict()
        capability = get_capability_entry(f'navigation.{provider}').to_dict()
        if lane['packageName'] != entry.package_name:
            errors.append(f'{provider}:package_mismatch')
        if lane['executable'] != entry.executable:
            errors.append(f'{provider}:executable_mismatch')
        if provider == 'nav2_provider':
            if lane['defaultSurfaceExposure'] != 'hidden_by_default':
                errors.append('nav2_provider:must_remain_hidden_by_default')
            missing_evidence = [item for item in entry.promotion_checklist if item not in lane['evidenceRequired']]
            if missing_evidence:
                errors.append(f'nav2_provider:missing_lane_evidence:{missing_evidence}')
        for non_claim in entry.non_claims:
            if non_claim not in capability.get('nonClaims', []):
                errors.append(f'{provider}:missing_capability_non_claim:{non_claim}')
    return errors
