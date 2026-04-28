from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from robot_contracts.capability_registry import get_capability_entry


def _capability_lifecycle_stage(capability_id: str) -> str:
    governance_stage = get_capability_entry(capability_id).governance_stage
    if governance_stage == 'mainline':
        return 'mainline'
    if governance_stage in {'experimental_gated', 'contract_only', 'evidence_only'}:
        return 'experimental'
    if governance_stage == 'rollback_only':
        return 'rollback_only'
    if governance_stage == 'mainline_with_experimental_lane_isolation':
        return 'mainline'
    return 'experimental'


@dataclass(frozen=True)
class LaneRegistryEntry:
    lane_id: str
    capability_id: str | None
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
    lifecycle_stage: str = 'mainline'
    default_surface_exposure: str = 'default_visible'
    retention_condition: str = 'mainline_required'
    exit_condition: str = 'not_applicable'

    def to_dict(self) -> dict[str, Any]:
        return {
            'laneId': self.lane_id,
            'capabilityId': self.capability_id,
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
            'lifecycleStage': self.lifecycle_stage,
            'defaultSurfaceExposure': self.default_surface_exposure,
            'retentionCondition': self.retention_condition,
            'exitCondition': self.exit_condition,
        }


def _lane_with_capability(*, lane_id: str, capability_id: str, owner: str, package_name: str, executable: str, child_factory: str, activation_decision: str, rollback_policy: str, evidence_required: tuple[str, ...] | None = None, upgrade_condition: str, description: str, visibility: str | None = None, retention_condition: str, exit_condition: str) -> LaneRegistryEntry:
    capability = get_capability_entry(capability_id)
    derived_visibility = visibility or ('experimental' if capability.ui_exposure_policy == 'hidden_by_default' else 'public')
    derived_evidence = tuple(evidence_required if evidence_required is not None else capability.evidence_artifacts)
    return LaneRegistryEntry(lane_id=lane_id, capability_id=capability_id, domain=capability.domain, owner=owner, package_name=package_name, executable=executable, child_factory=child_factory, activation_decision=activation_decision, rollback_policy=rollback_policy, evidence_required=derived_evidence, upgrade_condition=upgrade_condition, description=description, visibility=derived_visibility, lifecycle_stage=_capability_lifecycle_stage(capability_id), default_surface_exposure=capability.ui_exposure_policy, retention_condition=retention_condition, exit_condition=exit_condition)


_LANE_REGISTRY: dict[str, LaneRegistryEntry] = {
    'navigation.simple_nav_provider': _lane_with_capability(lane_id='navigation.simple_nav_provider', capability_id='navigation.simple_nav_provider', owner='robot_navigation', package_name='robot_navigation', executable='navigation_node', child_factory='robot_navigation.navigation_node:RobotNavigationNode', activation_decision='activate', rollback_policy='baseline_runtime_remains_default', upgrade_condition='mainline_baseline_provider_already_supported', description='Baseline waypoint navigation runtime hosted in robot_navigation.', retention_condition='baseline_navigation_provider_required_for_mainline', exit_condition='only_replaced_by_new_mainline_navigation_provider'),
    'navigation.nav2_provider': _lane_with_capability(lane_id='navigation.nav2_provider', capability_id='navigation.nav2_provider', owner='robot_nav2_adapter', package_name='robot_nav2_adapter', executable='nav2_adapter_node', child_factory='robot_nav2_adapter.nav2_adapter_node:Nav2AdapterNode', activation_decision='activate', rollback_policy='switch_provider_name_back_to_simple_nav_provider', upgrade_condition='adapter lane package installed and gate artifacts passing; stronger external-backend claims require backend integration evidence', description='Isolated local adapter backend lane with optional external backend contract; default in-package runtime remains the governed local adapter backend.', retention_condition='keep_until_external_backend_integration_and_acceptance_are_verified', exit_condition='promote_only_after_external_backend_smoke_and_target_environment_acceptance_are_verified'),
    'hardware.ros_projection_only': _lane_with_capability(lane_id='hardware.ros_projection_only', capability_id='hardware.ros_projection_only', owner='robot_hardware_interface', package_name='robot_hardware_interface', executable='hardware_interface_node', child_factory='robot_hardware_interface.hardware_interface_node:HardwareInterfaceNode', activation_decision='activate', rollback_policy='mainline_default_compatibility_surface', upgrade_condition='mainline_projection_surface_already_supported', description='Default ROS projection-only hardware compatibility surface.', retention_condition='mainline_projection_surface_required', exit_condition='only_removed_when_board_authority_is_re-architected'),
    'hardware.ros_soft_driver': _lane_with_capability(lane_id='hardware.ros_soft_driver', capability_id='hardware.ros_soft_driver', owner='robot_direct_driver', package_name='robot_direct_driver', executable='direct_driver_node', child_factory='robot_direct_driver.direct_driver_node:DirectDriverNode', activation_decision='activate', rollback_policy='switch_compatibility_surface_role_to_ros_projection_only', upgrade_condition='explicit ros_soft_driver profile selected; no board-execution claim may be made without verified_board_driver evidence', description='ROS-owned soft driver lane. It may run the driver transport loop but is not allowed to claim verified board execution.', visibility='experimental', retention_condition='keep_as_compatibility_lane_until_verified_board_driver_or_ros2_control_lane_replaces_it', exit_condition='remove_only_after_verified_board_driver_migration_and_rollback_window_close'),
    'hardware.verified_board_driver': _lane_with_capability(lane_id='hardware.verified_board_driver', capability_id='hardware.verified_board_driver', owner='robot_direct_driver', package_name='robot_direct_driver', executable='direct_driver_node', child_factory='robot_direct_driver.direct_driver_node:DirectDriverNode', activation_decision='activate', rollback_policy='fall_back_to_ros_soft_driver_or_ros_projection_only_by_explicit_profile_change', upgrade_condition='fresh HIL or target acceptance artifact bound to current source/config identity', description='Verified board-driver lane. Board-execution claims are allowed only after activation evidence passes identity-bound acceptance checks.', visibility='experimental', retention_condition='keep_separate_until_ros2_control_system_interface_lane_is_ready', exit_condition='promote_only_after_ros2_control_hardware_plugin_and_target_acceptance_close'),
    'hardware.direct_driver': _lane_with_capability(lane_id='hardware.direct_driver', capability_id='hardware.direct_driver', owner='robot_direct_driver', package_name='robot_direct_driver', executable='direct_driver_node', child_factory='robot_direct_driver.direct_driver_node:DirectDriverNode', activation_decision='rollback_only', rollback_policy='legacy alias only; configure ros_soft_driver or verified_board_driver explicitly', upgrade_condition='deprecated compatibility alias, not a primary role', description='Deprecated compatibility alias retained for old configs; new configs must use ros_soft_driver or verified_board_driver.', visibility='experimental', retention_condition='retain_until_legacy_direct_driver_configs_are_migrated', exit_condition='remove_after_legacy_config_window'),
    'bridge_runtime.split_runtime': LaneRegistryEntry(lane_id='bridge_runtime.split_runtime', capability_id=None, domain='bridge_runtime', owner='robot_bridge', package_name='robot_bridge', executable='bridge_transport_node', child_factory='robot_bridge.bridge_transport_node:BridgeTransportNode', activation_decision='activate', rollback_policy='fall_back_to_legacy_monolith_only_via_explicit_rollback_gate', evidence_required=('runtime_smoke',), upgrade_condition='mainline_default_runtime', description='Mainline split bridge runtime topology.', visibility='public', lifecycle_stage='mainline', default_surface_exposure='default_visible', retention_condition='mainline_bridge_runtime_required', exit_condition='only_replaced_by_new_mainline_bridge_runtime'),
    'bridge_runtime.legacy_monolith': LaneRegistryEntry(lane_id='bridge_runtime.legacy_monolith', capability_id=None, domain='bridge_runtime', owner='robot_bridge', package_name='robot_bridge', executable='bridge_node', child_factory='robot_bridge.bridge_node:BridgeNode', activation_decision='rollback_only', rollback_policy='must_be_explicitly_enabled_by_allow_legacy_bridge_runtime', evidence_required=('legacy_runtime_smoke',), upgrade_condition='kept_only_for_controlled_rollback', description='Legacy monolithic bridge runtime kept behind an explicit rollback gate.', visibility='experimental', lifecycle_stage='rollback_only', default_surface_exposure='hidden_by_default', retention_condition='retain_only_until_split_runtime_rollback_window_expires', exit_condition='remove_after_controlled_rollback_window_and_release_audit_close'),
}


def lane_registry_payload(*, include_experimental: bool = True) -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for lane_id, entry in _LANE_REGISTRY.items():
        if entry.visibility == 'experimental' and not include_experimental:
            continue
        payload[lane_id] = entry.to_dict()
    return payload


def get_lane_entry(lane_id: str) -> LaneRegistryEntry:
    normalized = str(lane_id or '').strip()
    if normalized not in _LANE_REGISTRY:
        raise ValueError(f'unsupported lane_id: {lane_id!r}')
    return _LANE_REGISTRY[normalized]


def navigation_lane_entry(provider_name: str) -> LaneRegistryEntry:
    normalized = str(provider_name or '').strip() or 'simple_nav_provider'
    if normalized == 'nav2_provider':
        return get_lane_entry('navigation.nav2_provider')
    if normalized == 'simple_nav_provider':
        return get_lane_entry('navigation.simple_nav_provider')
    raise ValueError(f'unsupported navigation provider: {provider_name!r}')


def hardware_lane_entry(compatibility_surface_role: str) -> LaneRegistryEntry:
    normalized = str(compatibility_surface_role or '').strip() or 'ros_projection_only'
    if normalized == 'direct_driver':
        return get_lane_entry('hardware.direct_driver')
    if normalized == 'ros_soft_driver':
        return get_lane_entry('hardware.ros_soft_driver')
    if normalized == 'verified_board_driver':
        return get_lane_entry('hardware.verified_board_driver')
    if normalized == 'ros_projection_only':
        return get_lane_entry('hardware.ros_projection_only')
    raise ValueError(f'unsupported hardware lane: {compatibility_surface_role!r}')


def bridge_runtime_lane_entry(runtime_mode: str) -> LaneRegistryEntry:
    normalized = str(runtime_mode or '').strip() or 'split_runtime'
    if normalized == 'legacy_monolith_runtime':
        return get_lane_entry('bridge_runtime.legacy_monolith')
    if normalized in {'split_runtime', 'split'}:
        return get_lane_entry('bridge_runtime.split_runtime')
    raise ValueError(f'unsupported bridge runtime lane: {runtime_mode!r}')
