from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from typing import Any

from robot_contracts.lane_registry import navigation_lane_entry


@dataclass(frozen=True)
class NavigationProviderContract:
    """Describe one navigation-provider contract exposed to decision/control.

    Args:
        provider_name: Stable provider identifier.
        supports_route_plan: Whether named route plans are supported.
        supports_goal_pose: Whether direct pose goals are supported.
        supports_goal_id: Whether named waypoint goals are supported.
        supports_cancel: Whether explicit cancel semantics are supported.
        path_preview_mode: Preview/path semantics emitted by the provider.
        execution_model: High-level execution model label.
        provider_lane: Stable lane classification used by runtime governance.
        route_authority: Which subsystem is authoritative for patrol motion/progress.
        fallback_behavior: Stable explanation of how the system behaves when the
            provider cannot be activated or becomes unavailable.
        integration_stage: Delivery stage of the backend implementation.
        implemented: Whether this provider is backed by executable runtime code.
        activation_policy: Stable explanation of how the provider may be activated.
    """

    provider_name: str
    supports_route_plan: bool
    supports_goal_pose: bool
    supports_goal_id: bool
    supports_cancel: bool
    path_preview_mode: str
    execution_model: str
    provider_lane: str
    route_authority: str
    fallback_behavior: str
    integration_stage: str
    implemented: bool
    activation_policy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'providerName': self.provider_name,
            'supportsRoutePlan': self.supports_route_plan,
            'supportsGoalPose': self.supports_goal_pose,
            'supportsGoalId': self.supports_goal_id,
            'supportsCancel': self.supports_cancel,
            'pathPreviewMode': self.path_preview_mode,
            'executionModel': self.execution_model,
            'providerLane': self.provider_lane,
            'routeAuthority': self.route_authority,
            'fallbackBehavior': self.fallback_behavior,
            'integrationStage': self.integration_stage,
            'implemented': self.implemented,
            'activationPolicy': self.activation_policy,
        }


_SIMPLE_PROVIDER = NavigationProviderContract(
    provider_name='simple_nav_provider',
    supports_route_plan=True,
    supports_goal_pose=True,
    supports_goal_id=True,
    supports_cancel=True,
    path_preview_mode='straight_line_preview',
    execution_model='single_node_proportional_controller',
    provider_lane='baseline_runtime',
    route_authority='navigation_runtime',
    fallback_behavior='mainline_supported_no_secondary_provider_required',
    integration_stage='mainline_supported',
    implemented=True,
    activation_policy='default_runtime_supported',
)

_NAV2_PROVIDER_EXPERIMENTAL = NavigationProviderContract(
    provider_name='nav2_provider',
    supports_route_plan=True,
    supports_goal_pose=True,
    supports_goal_id=False,
    supports_cancel=True,
    path_preview_mode='planner_server_path',
    execution_model='planner_controller_behavior_servers',
    provider_lane='separate_adapter_package',
    route_authority='navigation_runtime',
    fallback_behavior='switch_provider_name_back_to_simple_nav_provider_if_adapter_lane_is_unavailable',
    integration_stage='packaged_adapter_runtime',
    implemented=True,
    activation_policy='experimental_provider_runs_in_robot_nav2_adapter_package',
)

_PUBLIC_PROVIDER_REGISTRY = {
    _SIMPLE_PROVIDER.provider_name: _SIMPLE_PROVIDER,
}

_EXPERIMENTAL_PROVIDER_REGISTRY = {
    _NAV2_PROVIDER_EXPERIMENTAL.provider_name: _NAV2_PROVIDER_EXPERIMENTAL,
}

_ALL_PROVIDER_REGISTRY = {
    **_PUBLIC_PROVIDER_REGISTRY,
    **_EXPERIMENTAL_PROVIDER_REGISTRY,
}


def resolve_navigation_provider(name: str) -> NavigationProviderContract:
    """Resolve one provider contract by name.

    Args:
        name: Requested provider identifier.

    Returns:
        Provider contract snapshot.

    Raises:
        ValueError: If ``name`` is unsupported.
    """
    normalized = str(name or '').strip() or _SIMPLE_PROVIDER.provider_name
    if normalized not in _ALL_PROVIDER_REGISTRY:
        raise ValueError(f'unsupported navigation provider: {name!r}')
    return _ALL_PROVIDER_REGISTRY[normalized]



def _provider_package_available(provider: NavigationProviderContract) -> bool:
    """Return whether the requested provider lane package is importable.

    Args:
        provider: Resolved provider contract.

    Returns:
        ``True`` when the lane package referenced by the governance registry is
        importable in the current runtime environment.

    Raises:
        None. Unknown providers are handled by ``resolve_navigation_provider``.
    """
    lane = navigation_lane_entry(provider.provider_name)
    return importlib.util.find_spec(lane.package_name) is not None


def ensure_provider_runtime_supported(provider: NavigationProviderContract) -> NavigationProviderContract:
    """Fail fast when a provider contract is declared but its lane package is missing."""
    if provider.implemented and _provider_package_available(provider):
        return provider
    raise NotImplementedError(
        f'navigation provider {provider.provider_name!r} is not packaged in the current runtime; '
        f'activation policy={provider.activation_policy}'
    )



def navigation_provider_registry_payload(*, include_experimental: bool = False) -> dict[str, Any]:
    """Return the serializable provider registry exposed to the current surface."""
    registry = dict(_PUBLIC_PROVIDER_REGISTRY)
    if include_experimental:
        registry.update(_EXPERIMENTAL_PROVIDER_REGISTRY)
    return {name: contract.to_dict() for name, contract in registry.items()}



def navigation_provider_activation(provider_name: str) -> dict[str, Any]:
    """Describe whether one configured provider may be activated.

    Args:
        provider_name: Requested provider identifier from navigation config.

    Returns:
        Serializable activation payload including governance-lane metadata.

    Raises:
        ValueError: If ``provider_name`` is unsupported.
    """
    provider = resolve_navigation_provider(provider_name)
    lane = navigation_lane_entry(provider.provider_name)
    runtime_supported = bool(provider.implemented and _provider_package_available(provider))
    provider_visibility = 'experimental' if provider.provider_name in _EXPERIMENTAL_PROVIDER_REGISTRY else 'public'
    return {
        'requestedProvider': provider_name,
        'resolvedProvider': provider.to_dict(),
        'runtimeSupported': runtime_supported,
        'mainlineEligible': runtime_supported and provider.provider_lane == 'baseline_runtime',
        'rollbackEligible': True,
        'providerVisibility': provider_visibility,
        'activationDecision': 'activate' if runtime_supported else 'reject',
        'blockingReason': None if runtime_supported else provider.activation_policy,
        'governanceLane': lane.to_dict(),
        'availableProviders': navigation_provider_registry_payload(),
        'declaredExperimentalProviders': navigation_provider_registry_payload(include_experimental=True),
    }
