from __future__ import annotations

"""Pure-Python backend-claim resolver for the experimental navigation adapter lane."""

from typing import Any


SUPPORTED_BACKEND_MODES = {'auto', 'local_adapter', 'external_nav2_stack'}


def resolve_nav2_backend_runtime_claims(
    *,
    requested_backend_mode: str,
    external_nav2_stack_available: bool,
    external_nav2_backend_integrated: bool,
    recovery_enabled: bool,
) -> dict[str, Any]:
    """Resolve truthful runtime claims for the nav2 adapter lane.

    Args:
        requested_backend_mode: Requested backend selector.
        external_nav2_stack_available: Whether the environment advertises an
            external Nav2 stack.
        external_nav2_backend_integrated: Whether this package has an actual
            backend integration capable of driving that external stack.
        recovery_enabled: Whether local recovery signaling is enabled.

    Returns:
        Serializable runtime-claim mapping.

    Raises:
        None. Unsupported backend values fall back to ``auto`` semantics.

    Boundary behavior:
        External availability alone is not enough to claim backend integration.
        The external backend may only be selected when both runtime availability
        and concrete integration support are true.
    """
    requested = str(requested_backend_mode or 'auto').strip() or 'auto'
    if requested not in SUPPORTED_BACKEND_MODES:
        requested = 'auto'
    external_selectable = bool(external_nav2_stack_available and external_nav2_backend_integrated)
    if requested == 'external_nav2_stack' and external_selectable:
        selected = 'external_nav2_stack'
    elif requested == 'external_nav2_stack':
        selected = 'local_adapter'
    elif requested == 'auto':
        selected = 'external_nav2_stack' if external_selectable else 'local_adapter'
    else:
        selected = 'local_adapter'
    fallback_applied = selected != requested and requested != 'auto'
    external_selected = selected == 'external_nav2_stack'
    return {
        'requestedBackend': requested,
        'selectedBackend': selected,
        'fallbackApplied': fallback_applied,
        'governanceReady': True,
        'activationGateManagedOutsideNode': True,
        'externalRuntimeAdvertised': bool(external_nav2_stack_available),
        'externalBackendIntegrated': bool(external_nav2_backend_integrated),
        'backendIntegrated': external_selected and bool(external_nav2_backend_integrated),
        'nav2RuntimeAvailable': external_selected and bool(external_nav2_stack_available),
        'localAdapterRuntimeAvailable': True,
        'mapSupport': external_selected and bool(external_nav2_backend_integrated),
        'localizationSupport': external_selected and bool(external_nav2_backend_integrated),
        'plannerSupport': external_selected and bool(external_nav2_backend_integrated),
        'controllerSupport': external_selected and bool(external_nav2_backend_integrated),
        'recoverySupport': bool(recovery_enabled),
        'routeSupport': True,
        'cancelSupport': True,
        'healthSupport': True,
        'acceptanceStagesRequired': ['simulation', 'host_harness', 'target_environment', 'operator_docs'],
        'notes': (
            'experimental lane is governed and runnable, but only the local_adapter backend is implemented '
            'inside this package unless external_nav2_backend_integrated=true'
        ),
    }
