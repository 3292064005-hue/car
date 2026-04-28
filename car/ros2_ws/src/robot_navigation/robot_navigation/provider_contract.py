from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from typing import Any, Protocol, runtime_checkable

from robot_contracts.capability_registry import get_capability_entry
from robot_contracts.lane_registry import navigation_lane_entry
from robot_contracts.navigation_adapter_boundary_registry import navigation_adapter_boundary_entry
from robot_navigation.navigation_acceptance import nav2_external_backend_smoke_required, validate_nav2_acceptance_gate




@runtime_checkable
class NavigationProviderRuntime(Protocol):
    """Runtime interface every navigation provider lane must implement.

    Methods:
        readiness: Return provider readiness and blocking reason.
        load_route: Load a named route before execution.
        start_route: Start or resume route execution.
        pause: Temporarily stop route execution without clearing route state.
        resume: Resume a paused route.
        cancel: Cancel active route execution and return a terminal status.
        get_status: Return the normalized provider status payload.

    Raises:
        Provider implementations may raise provider-specific exceptions;
        callers must convert them to ``blocked`` or ``failed`` lifecycle
        states before publishing product-visible status.

    Boundary behavior:
        The protocol is intentionally independent of Nav2 action classes
        so the simple provider remains the stable rollback lane while a
        Nav2 provider can map ``NavigateThroughPoses`` feedback/results
        into the same project lifecycle vocabulary.
    """

    def readiness(self) -> dict[str, Any]:
        ...

    def load_route(self, route_name: str) -> dict[str, Any]:
        ...

    def start_route(self, route_name: str) -> dict[str, Any]:
        ...

    def pause(self) -> dict[str, Any]:
        ...

    def resume(self) -> dict[str, Any]:
        ...

    def cancel(self) -> dict[str, Any]:
        ...

    def get_status(self) -> dict[str, Any]:
        ...

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
        capabilities: Stable capability descriptors exposed by the provider lane.
        acceptance_stages: Required evidence stages before stronger claims are made.
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
    capabilities: tuple[str, ...] = ()
    acceptance_stages: tuple[str, ...] = ()

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
            'capabilities': list(self.capabilities),
            'acceptanceStages': list(self.acceptance_stages),
            'runtimeInterface': ['readiness', 'load_route', 'start_route', 'pause', 'resume', 'cancel', 'get_status'],
        }



def _provider_capability_entry(provider_name: str):
    if provider_name == 'nav2_provider':
        return get_capability_entry('navigation.nav2_provider')
    return get_capability_entry('navigation.simple_nav_provider')




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
    integration_stage=_provider_capability_entry('simple_nav_provider').implementation_status,
    implemented=True,
    activation_policy='default_runtime_supported',
    capabilities=('route', 'goal_pose', 'goal_id', 'cancel', 'health', 'path_preview'),
    acceptance_stages=('host_harness',),
)

_NAV2_PROVIDER_EXPERIMENTAL = NavigationProviderContract(
    provider_name='nav2_provider',
    supports_route_plan=True,
    supports_goal_pose=True,
    supports_goal_id=True,
    supports_cancel=True,
    path_preview_mode='local_adapter_path_preview',
    execution_model='isolated_local_adapter_lane_with_optional_external_backend_contract',
    provider_lane='separate_adapter_package',
    route_authority='navigation_runtime',
    fallback_behavior='operator_may_switch_provider_name_back_to_simple_nav_provider_when_adapter_lane_is_unhealthy',
    integration_stage=_provider_capability_entry('nav2_provider').implementation_status,
    implemented=True,
    activation_policy='experimental_local_adapter_requires_explicit_gate',
    capabilities=('route', 'goal_pose', 'goal_id', 'cancel', 'health', 'local_adapter_path_preview'),
    acceptance_stages=('simulation', 'host_harness', 'target_environment', 'operator_docs'),
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
    boundary = navigation_adapter_boundary_entry(provider.provider_name)
    if boundary is None:
        lane = navigation_lane_entry(provider.provider_name)
        package_name = lane.package_name
    else:
        package_name = boundary.package_name
    return importlib.util.find_spec(package_name) is not None



def ensure_provider_runtime_supported(provider: NavigationProviderContract) -> NavigationProviderContract:
    """Fail fast when a provider contract is declared but its lane package is missing.

    Args:
        provider: Resolved provider contract.

    Returns:
        The original provider when its runtime lane is importable.

    Raises:
        NotImplementedError: The requested provider is declared in governance but
            its package is unavailable in the current runtime environment.
    """
    if provider.implemented and _provider_package_available(provider):
        return provider
    raise NotImplementedError(
        f'navigation provider {provider.provider_name!r} is not runtime-supported in the current environment; '
        f'activation policy={provider.activation_policy}'
    )



def navigation_provider_registry_payload(*, include_experimental: bool = False) -> dict[str, Any]:
    """Return the serializable provider registry exposed to the current surface."""
    registry = dict(_PUBLIC_PROVIDER_REGISTRY)
    if include_experimental:
        registry.update(_EXPERIMENTAL_PROVIDER_REGISTRY)
    return {name: contract.to_dict() for name, contract in registry.items()}



def navigation_provider_activation(
    provider_name: str,
    *,
    allow_experimental: bool = False,
    acceptance_artifact_paths: dict[str, str] | None = None,
    reference_config_path: str | None = None,
    require_external_backend_smoke: bool = False,
) -> dict[str, Any]:
    """Describe whether one configured provider may be activated.

    Args:
        provider_name: Requested provider identifier from navigation config.
        allow_experimental: Whether experimental providers may be activated in the
            current launch/runtime surface after explicit operator approval.

    Returns:
        Serializable activation payload including governance-lane metadata and
        selected runtime fallback information.

    Raises:
        ValueError: If ``provider_name`` is unsupported.
    """
    requested_provider = resolve_navigation_provider(provider_name)
    requested_lane = navigation_lane_entry(requested_provider.provider_name)
    requested_boundary = navigation_adapter_boundary_entry(requested_provider.provider_name)
    runtime_supported = bool(requested_provider.implemented and _provider_package_available(requested_provider))
    provider_visibility = 'experimental' if requested_provider.provider_name in _EXPERIMENTAL_PROVIDER_REGISTRY else 'public'
    experimental_requested = provider_visibility == 'experimental'

    selected_provider = requested_provider
    selected_lane = requested_lane
    selected_boundary = requested_boundary
    selected_runtime_reason = 'requested_provider_runtime_available'
    activation_decision = 'activate'
    blocking_reason = None
    acceptance_gate = None
    if not runtime_supported:
        selected_provider = _SIMPLE_PROVIDER
        selected_lane = navigation_lane_entry(selected_provider.provider_name)
        selected_boundary = navigation_adapter_boundary_entry(selected_provider.provider_name)
        selected_runtime_reason = 'fallback_to_simple_nav_provider_mainline'
        activation_decision = 'reject'
        blocking_reason = requested_provider.activation_policy
    elif experimental_requested and not allow_experimental:
        selected_provider = _SIMPLE_PROVIDER
        selected_lane = navigation_lane_entry(selected_provider.provider_name)
        selected_boundary = navigation_adapter_boundary_entry(selected_provider.provider_name)
        selected_runtime_reason = 'fallback_to_simple_nav_provider_until_experimental_gate_is_explicitly_enabled'
        activation_decision = 'reject'
        blocking_reason = 'experimental_provider_requires_explicit_allow_flag'
    elif experimental_requested:
        acceptance_gate = validate_nav2_acceptance_gate(
            acceptance_artifact_paths,
            config_root=reference_config_path,
            require_external_backend_smoke=require_external_backend_smoke,
        )
        if not acceptance_gate.valid:
            selected_provider = _SIMPLE_PROVIDER
            selected_lane = navigation_lane_entry(selected_provider.provider_name)
            selected_boundary = navigation_adapter_boundary_entry(selected_provider.provider_name)
            selected_runtime_reason = 'fallback_to_simple_nav_provider_until_experimental_acceptance_gate_passes'
            activation_decision = 'reject'
            blocking_reason = 'experimental_provider_acceptance_artifacts_incomplete'

    return {
        'requestedProvider': provider_name,
        'resolvedProvider': requested_provider.to_dict(),
        'runtimeSupported': runtime_supported,
        'mainlineEligible': runtime_supported and bool(requested_boundary.default_mainline if requested_boundary is not None else requested_provider.provider_lane == 'baseline_runtime'),
        'rollbackEligible': bool(requested_boundary.rollback_baseline if requested_boundary is not None else True),
        'providerVisibility': provider_visibility,
        'experimentalGatePassed': (not experimental_requested) or bool(allow_experimental),
        'acceptanceGatePassed': (not experimental_requested) or bool(acceptance_gate.valid if acceptance_gate is not None else False),
        'acceptanceGate': acceptance_gate.to_dict() if acceptance_gate is not None else None,
        'requireExternalBackendSmoke': bool(require_external_backend_smoke),
        'governanceReady': runtime_supported,
        'laneGateReady': bool(allow_experimental) if experimental_requested else True,
        'backendIntegrated': False if requested_provider.provider_name == 'nav2_provider' else True,
        'targetAccepted': bool(acceptance_gate.valid if acceptance_gate is not None else False) if experimental_requested else False,
        'capabilityTruth': _provider_capability_entry(requested_provider.provider_name).to_dict(),
        'activationDecision': activation_decision,
        'blockingReason': blocking_reason,
        'capabilities': list(requested_provider.capabilities),
        'acceptanceStages': list(requested_provider.acceptance_stages),
        'governanceLane': requested_lane.to_dict(),
        'governanceBoundary': requested_boundary.to_dict() if requested_boundary is not None else None,
        'selectedRuntimeProvider': selected_provider.provider_name,
        'selectedRuntimePackage': selected_boundary.package_name if selected_boundary is not None else selected_lane.package_name,
        'selectedRuntimeExecutable': selected_boundary.executable if selected_boundary is not None else selected_lane.executable,
        'selectedRuntimeReason': selected_runtime_reason,
        'selectedGovernanceLane': selected_lane.to_dict(),
        'selectedGovernanceBoundary': selected_boundary.to_dict() if selected_boundary is not None else None,
        'availableProviders': navigation_provider_registry_payload(),
        'declaredExperimentalProviders': navigation_provider_registry_payload(include_experimental=True),
    }
