from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LaneRegistryEntry:
    """Stable governance description for one experimental or mainline lane.

    Args:
        lane_id: Stable unique lane identifier.
        domain: Governance domain such as ``navigation`` or ``hardware``.
        owner: Owning subsystem or package family.
        package_name: Runtime package providing the lane implementation.
        executable: Console entry point for non-lifecycle launches.
        child_factory: Child-factory path for lifecycle launches.
        activation_decision: Default activation decision when the lane is
            requested and its package is available.
        rollback_policy: Stable rollback guidance exposed to reports.
        evidence_required: Artifact classes that must exist before the lane may
            claim stronger execution semantics.
        upgrade_condition: Stable rule for promoting the lane.
        description: Human-readable summary.
        visibility: ``public`` or ``experimental``.
    """

    lane_id: str
    domain: str
    owner: str
    package_name: str
    executable: str
    child_factory: str
    activation_decision: str
    rollback_policy: str
    evidence_required: tuple[str, ...]
    upgrade_condition: str
    description: str
    visibility: str = 'public'

    def to_dict(self) -> dict[str, Any]:
        return {
            'laneId': self.lane_id,
            'domain': self.domain,
            'owner': self.owner,
            'packageName': self.package_name,
            'executable': self.executable,
            'childFactory': self.child_factory,
            'activationDecision': self.activation_decision,
            'rollbackPolicy': self.rollback_policy,
            'evidenceRequired': list(self.evidence_required),
            'upgradeCondition': self.upgrade_condition,
            'description': self.description,
            'visibility': self.visibility,
        }


_LANE_REGISTRY: dict[str, LaneRegistryEntry] = {
    'navigation.simple_nav_provider': LaneRegistryEntry(
        lane_id='navigation.simple_nav_provider',
        domain='navigation',
        owner='robot_navigation',
        package_name='robot_navigation',
        executable='navigation_node',
        child_factory='robot_navigation.navigation_node:RobotNavigationNode',
        activation_decision='activate',
        rollback_policy='baseline_runtime_remains_default',
        evidence_required=('host_harness_smoke',),
        upgrade_condition='mainline_baseline_provider_already_supported',
        description='Baseline waypoint navigation runtime hosted in robot_navigation.',
        visibility='public',
    ),
    'navigation.nav2_provider': LaneRegistryEntry(
        lane_id='navigation.nav2_provider',
        domain='navigation',
        owner='robot_nav2_adapter',
        package_name='robot_nav2_adapter',
        executable='nav2_adapter_node',
        child_factory='robot_nav2_adapter.nav2_adapter_node:Nav2AdapterNode',
        activation_decision='activate',
        rollback_policy='switch_provider_name_back_to_simple_nav_provider',
        evidence_required=('adapter_smoke', 'provider_switch_smoke'),
        upgrade_condition='separate adapter package installed and provider smoke passing',
        description='Separate navigation adapter lane that isolates experimental Nav2-oriented integration from the baseline provider.',
        visibility='experimental',
    ),
    'hardware.ros_projection_only': LaneRegistryEntry(
        lane_id='hardware.ros_projection_only',
        domain='hardware',
        owner='robot_hardware_interface',
        package_name='robot_hardware_interface',
        executable='hardware_interface_node',
        child_factory='robot_hardware_interface.hardware_interface_node:RobotHardwareInterfaceNode',
        activation_decision='activate',
        rollback_policy='keep_projection_surface_as_default',
        evidence_required=('host_harness_smoke',),
        upgrade_condition='not_applicable_projection_surface_is_mainline_default',
        description='Projection-only hardware compatibility surface.',
        visibility='public',
    ),
    'hardware.direct_driver': LaneRegistryEntry(
        lane_id='hardware.direct_driver',
        domain='hardware',
        owner='robot_direct_driver',
        package_name='robot_direct_driver',
        executable='direct_driver_node',
        child_factory='robot_direct_driver.direct_driver_node:DirectDriverNode',
        activation_decision='activate',
        rollback_policy='switch_compatibility_surface_role_to_ros_projection_only',
        evidence_required=('target_environment_acceptance',),
        upgrade_condition='separate driver lane package installed with acceptance artifact and profile smoke passing',
        description='Dedicated direct-driver lane that owns command/state authority inside a separate package.',
        visibility='experimental',
    ),
    'bridge_runtime.split_runtime': LaneRegistryEntry(
        lane_id='bridge_runtime.split_runtime',
        domain='bridge_runtime',
        owner='robot_bridge',
        package_name='robot_bridge',
        executable='bridge_transport_node',
        child_factory='robot_bridge.bridge_transport_node:BridgeTransportNode',
        activation_decision='activate',
        rollback_policy='fall_back_to_legacy_monolith_only_via_explicit_rollback_gate',
        evidence_required=('runtime_smoke',),
        upgrade_condition='mainline_default_runtime',
        description='Mainline split bridge runtime topology.',
        visibility='public',
    ),
    'bridge_runtime.legacy_monolith': LaneRegistryEntry(
        lane_id='bridge_runtime.legacy_monolith',
        domain='bridge_runtime',
        owner='robot_bridge',
        package_name='robot_bridge',
        executable='bridge_node',
        child_factory='robot_bridge.bridge_node:BridgeNode',
        activation_decision='rollback_only',
        rollback_policy='must_be_explicitly_enabled_by_allow_legacy_bridge_runtime',
        evidence_required=('legacy_runtime_smoke',),
        upgrade_condition='kept_only_for_controlled_rollback',
        description='Legacy monolithic bridge runtime kept behind an explicit rollback gate.',
        visibility='experimental',
    ),
}


def lane_registry_payload(*, include_experimental: bool = True) -> dict[str, dict[str, Any]]:
    """Return the serializable lane registry.

    Args:
        include_experimental: Whether experimental lanes should be included.

    Returns:
        Mapping keyed by stable lane identifier.

    Raises:
        None.
    """
    payload: dict[str, dict[str, Any]] = {}
    for lane_id, entry in _LANE_REGISTRY.items():
        if entry.visibility == 'experimental' and not include_experimental:
            continue
        payload[lane_id] = entry.to_dict()
    return payload



def get_lane_entry(lane_id: str) -> LaneRegistryEntry:
    """Resolve one lane by its stable identifier."""
    normalized = str(lane_id or '').strip()
    if normalized not in _LANE_REGISTRY:
        raise ValueError(f'unsupported lane_id: {lane_id!r}')
    return _LANE_REGISTRY[normalized]



def navigation_lane_entry(provider_name: str) -> LaneRegistryEntry:
    """Return the lane entry for one navigation provider name."""
    normalized = str(provider_name or '').strip() or 'simple_nav_provider'
    if normalized == 'nav2_provider':
        return get_lane_entry('navigation.nav2_provider')
    if normalized == 'simple_nav_provider':
        return get_lane_entry('navigation.simple_nav_provider')
    raise ValueError(f'unsupported navigation provider: {provider_name!r}')



def hardware_lane_entry(compatibility_surface_role: str) -> LaneRegistryEntry:
    """Return the lane entry for one hardware boundary role."""
    normalized = str(compatibility_surface_role or '').strip() or 'ros_projection_only'
    if normalized == 'direct_driver':
        return get_lane_entry('hardware.direct_driver')
    if normalized == 'ros_projection_only':
        return get_lane_entry('hardware.ros_projection_only')
    raise ValueError(f'unsupported hardware lane: {compatibility_surface_role!r}')



def bridge_runtime_lane_entry(runtime_mode: str) -> LaneRegistryEntry:
    """Return the lane entry for one bridge runtime mode label."""
    normalized = str(runtime_mode or '').strip() or 'split_runtime'
    if normalized == 'legacy_monolith_runtime':
        return get_lane_entry('bridge_runtime.legacy_monolith')
    if normalized in {'split_runtime', 'split'}:
        return get_lane_entry('bridge_runtime.split_runtime')
    raise ValueError(f'unsupported bridge runtime lane: {runtime_mode!r}')
