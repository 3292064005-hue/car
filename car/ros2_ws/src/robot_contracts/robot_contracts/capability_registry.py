from __future__ import annotations

"""Single-source capability registry for governance, runtime claims, UI maturity, and release notes.

This registry intentionally separates frequently conflated concepts:

- governance stage: whether the repository allows a lane/capability to exist;
- implementation status: what backend/runtime is actually implemented today;
- acceptance stage: which evidence level is required before stronger claims are made;
- frontend maturity: how the capability may be summarized on operator surfaces.

Provider contracts, lane registry views, generated frontend governance artifacts,
feature-maturity pills, and release-note drift checks should consume this registry
instead of hand-writing parallel maturity strings.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CapabilityRegistryEntry:
    """Stable registry entry for one user-visible capability or lane."""

    capability_id: str
    title: str
    domain: str
    implementation_status: str
    governance_stage: str
    acceptance_stage: str
    ui_exposure_policy: str
    frontend_maturity: str
    release_note_policy: str
    truth_source_paths: tuple[str, ...]
    evidence_artifacts: tuple[str, ...] = ()
    external_dependencies: tuple[str, ...] = ()
    entry_surfaces: tuple[str, ...] = ()
    runtime_claims: tuple[str, ...] = ()
    non_claims: tuple[str, ...] = ()
    operator_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            'capabilityId': self.capability_id,
            'title': self.title,
            'domain': self.domain,
            'implementationStatus': self.implementation_status,
            'governanceStage': self.governance_stage,
            'acceptanceStage': self.acceptance_stage,
            'uiExposurePolicy': self.ui_exposure_policy,
            'frontendMaturity': self.frontend_maturity,
            'releaseNotePolicy': self.release_note_policy,
            'truthSourcePaths': list(self.truth_source_paths),
            'evidenceArtifacts': list(self.evidence_artifacts),
            'externalDependencies': list(self.external_dependencies),
            'entrySurfaces': list(self.entry_surfaces),
            'runtimeClaims': list(self.runtime_claims),
            'nonClaims': list(self.non_claims),
            'operatorNotes': list(self.operator_notes),
        }


_CAPABILITY_REGISTRY: dict[str, CapabilityRegistryEntry] = {
    'navigation.simple_nav_provider': CapabilityRegistryEntry(
        capability_id='navigation.simple_nav_provider',
        title='主线导航 provider',
        domain='navigation',
        implementation_status='backend_integrated_mainline',
        governance_stage='mainline',
        acceptance_stage='host_harness_verified',
        ui_exposure_policy='default_visible',
        frontend_maturity='mainline',
        release_note_policy='stable_mainline_claims_allowed',
        truth_source_paths=(
            'ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py',
            'ros2_ws/src/robot_navigation/robot_navigation/navigation_node.py',
        ),
        evidence_artifacts=('host_harness_smoke',),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('route', 'goal_pose', 'goal_id', 'cancel', 'health', 'path_preview'),
        non_claims=('does_not_claim_external_nav2_stack',),
        operator_notes=('simple_nav_provider 是默认主线与回滚基线。',),
    ),
    'navigation.nav2_provider': CapabilityRegistryEntry(
        capability_id='navigation.nav2_provider',
        title='隔离导航 adapter lane',
        domain='navigation',
        implementation_status='governed_local_adapter_runtime',
        governance_stage='experimental_gated',
        acceptance_stage='simulation_host_harness_operator_docs_and_target_environment_required_for_lane_activation',
        ui_exposure_policy='hidden_by_default',
        frontend_maturity='mainline',
        release_note_policy='must_include_backend_non_claims',
        truth_source_paths=(
            'ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py',
            'ros2_ws/src/robot_navigation/robot_navigation/navigation_acceptance.py',
            'ros2_ws/src/robot_nav2_adapter/robot_nav2_adapter/backend_claims.py',
            'ros2_ws/src/robot_nav2_adapter/robot_nav2_adapter/nav2_adapter_node.py',
            'docs/release_notes/2026-04-patchD.md',
        ),
        evidence_artifacts=('simulation_smoke', 'host_harness_smoke', 'provider_switch_smoke', 'operator_docs_review', 'target_environment_acceptance', 'external_backend_smoke'),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('provider_neutral_route_execution', 'local_adapter_path_preview', 'local_adapter_health', 'gated_lane_activation'),
        non_claims=(
            'does_not_claim_external_nav2_backend_integration_when_running_local_adapter',
            'does_not_claim_nav2_planner_controller_recovery_servers_present_without_backend_integration',
        ),
        operator_notes=('该 lane 当前是受 gate 约束的本地 adapter runtime，不应被表述为已完成外部 Nav2 后端集成。',),
    ),
    'hardware.ros_projection_only': CapabilityRegistryEntry(
        capability_id='hardware.ros_projection_only',
        title='ROS 投影视图硬件边界',
        domain='hardware',
        implementation_status='mainline_projection_surface',
        governance_stage='mainline',
        acceptance_stage='host_harness_verified',
        ui_exposure_policy='default_visible',
        frontend_maturity='mainline',
        release_note_policy='stable_mainline_claims_allowed',
        truth_source_paths=(
            'ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_adapter.py',
            'ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_contract.py',
        ),
        evidence_artifacts=('host_harness_smoke',),
        entry_surfaces=('frontend_api_facade', 'bridge_observer_surface'),
        runtime_claims=('projection_surface', 'telemetry_projection', 'summary_contract'),
        non_claims=('does_not_claim_board_command_authority_inside_ros',),
        operator_notes=('projection-only lane 作为兼容/回滚面保留，不再是默认硬件主线。',),
    ),
    'hardware.ros_soft_driver': CapabilityRegistryEntry(
        capability_id='hardware.ros_soft_driver',
        title='ROS 软驱动硬件边界',
        domain='hardware',
        implementation_status='ros_soft_driver_no_verified_board_claim',
        governance_stage='experimental_gated',
        acceptance_stage='host_harness_or_operator_selected_real_robot_soft_driver',
        ui_exposure_policy='hidden_by_default',
        frontend_maturity='limited',
        release_note_policy='must_include_board_execution_non_claims',
        truth_source_paths=(
            'ros2_ws/src/robot_direct_driver/robot_direct_driver/direct_driver_node.py',
            'ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_adapter.py',
            'ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_activation.py',
        ),
        evidence_artifacts=('host_harness_smoke', 'runtime_signal_matrix_report'),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('ros_owned_soft_driver_loop', 'driver_lane_summary_contract'),
        non_claims=('does_not_claim_verified_board_execution', 'does_not_claim_target_acceptance'),
        operator_notes=('ros_soft_driver 可运行软驱动/传输循环，但不是已验板级执行闭环。',),
    ),
    'hardware.verified_board_driver': CapabilityRegistryEntry(
        capability_id='hardware.verified_board_driver',
        title='已验板级驱动 lane',
        domain='hardware',
        implementation_status='verified_board_driver_acceptance_gated',
        governance_stage='experimental_gated',
        acceptance_stage='hardware_in_loop_or_target_acceptance_required_for_board_execution_claims',
        ui_exposure_policy='hidden_by_default',
        frontend_maturity='limited',
        release_note_policy='must_bind_activation_to_fresh_acceptance_evidence',
        truth_source_paths=(
            'ros2_ws/src/robot_direct_driver/robot_direct_driver/direct_driver_node.py',
            'ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_adapter.py',
            'ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_activation.py',
            'ros2_ws/src/robot_hardware_interface/robot_hardware_interface/standardization_target.py',
        ),
        evidence_artifacts=('hardware_in_loop_acceptance', 'runtime_signal_matrix_report', 'target_environment_acceptance'),
        external_dependencies=('verified_board_runtime_or_hil_bench',),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('board_execution_claims_with_verified_acceptance', 'verified_transport_ack_heartbeat_fault_contract'),
        non_claims=('does_not_claim_board_execution_when_acceptance_identity_is_stale',),
        operator_notes=('verified_board_driver 是唯一可承载板级执行声明的 lane；缺少新鲜 acceptance 时必须拒绝激活。',),
    ),
    'hardware.direct_driver': CapabilityRegistryEntry(
        capability_id='hardware.direct_driver',
        title='旧 direct-driver 兼容别名',
        domain='hardware',
        implementation_status='deprecated_compatibility_alias',
        governance_stage='rollback_only',
        acceptance_stage='not_a_claim_source_use_ros_soft_driver_or_verified_board_driver',
        ui_exposure_policy='hidden_by_default',
        frontend_maturity='deprecated',
        release_note_policy='must_not_use_as_primary_board_execution_claim',
        truth_source_paths=(
            'ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_activation.py',
            'ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_adapter.py',
        ),
        evidence_artifacts=(),
        entry_surfaces=(),
        runtime_claims=('legacy_config_compatibility_alias',),
        non_claims=('does_not_define_a_primary_hardware_lane',),
        operator_notes=('direct_driver 仅作为旧配置兼容别名保留，新配置必须显式使用 ros_soft_driver 或 verified_board_driver。',),
    ),
    'operator.mode_switch': CapabilityRegistryEntry(
        capability_id='operator.mode_switch',
        title='模式切换',
        domain='operator',
        implementation_status='mainline_operator_command_path',
        governance_stage='mainline',
        acceptance_stage='host_harness_verified',
        ui_exposure_policy='default_visible',
        frontend_maturity='mainline',
        release_note_policy='stable_mainline_claims_allowed',
        truth_source_paths=('ros2_ws/src/robot_web_bridge/robot_web_bridge/components/command_handlers.py', 'robot_frontend/src/components/ModePanel.tsx'),
        evidence_artifacts=('host_harness_smoke',),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('authoritative_write_surface_9100',),
        non_claims=('does_not_claim_board_side_mode_execution_evidence',),
        operator_notes=('9100 API facade 是唯一权威写入口。',),
    ),
    'operator.teleop_control': CapabilityRegistryEntry(
        capability_id='operator.teleop_control',
        title='手动遥控',
        domain='operator',
        implementation_status='mainline_operator_command_path',
        governance_stage='mainline',
        acceptance_stage='target_environment_acceptance_required_for_board_motion_claims',
        ui_exposure_policy='default_visible',
        frontend_maturity='mainline',
        release_note_policy='must_include_target_acceptance_scope',
        truth_source_paths=('ros2_ws/src/robot_web_bridge/robot_web_bridge/components/command_handlers.py', 'robot_frontend/src/components/TeleopPanel.tsx'),
        evidence_artifacts=('host_harness_smoke', 'command_audit_report', 'target_environment_acceptance'),
        external_dependencies=('board_boundary_contract_or_verified_board_runtime',),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('authoritative_write_surface_9100', 'manual_cmd_vel_path'),
        non_claims=('does_not_claim_real_board_motion_acceptance_without_target_environment_acceptance',),
        operator_notes=('9001 observer 面必须拒绝写命令。',),
    ),
    'operator.safety_recovery': CapabilityRegistryEntry(
        capability_id='operator.safety_recovery',
        title='急停与恢复',
        domain='operator',
        implementation_status='mainline_operator_command_path',
        governance_stage='mainline',
        acceptance_stage='target_environment_acceptance_required_for_line_level_latency_claims',
        ui_exposure_policy='default_visible',
        frontend_maturity='mainline',
        release_note_policy='must_include_target_acceptance_scope',
        truth_source_paths=('ros2_ws/src/robot_web_bridge/robot_web_bridge/components/command_handlers.py', 'robot_frontend/src/components/FaultPanel.tsx'),
        evidence_artifacts=('host_harness_smoke', 'command_audit_report', 'target_environment_acceptance'),
        external_dependencies=('board_boundary_contract_or_verified_board_runtime',),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('emergency_stop_route', 'recovery_route'),
        non_claims=('does_not_claim_hardware_line_level_estop_latency_inside_this_repo',),
        operator_notes=('安全命令允许 soft-warn 旁路，但最终裁决以后端 ACK 为准。',),
    ),
    'operator.patrol_execution': CapabilityRegistryEntry(
        capability_id='operator.patrol_execution',
        title='巡检执行',
        domain='operator',
        implementation_status='mainline_orchestrator_with_experimental_navigation_lane_option',
        governance_stage='mainline_with_experimental_lane_isolation',
        acceptance_stage='simulation_host_harness_target_environment_and_operator_docs_required',
        ui_exposure_policy='default_visible',
        frontend_maturity='mainline_with_experimental_lane_isolation',
        release_note_policy='must_preserve_navigation_lane_truth',
        truth_source_paths=('ros2_ws/src/robot_decision/robot_decision/mission_orchestrator.py', 'ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py', 'robot_frontend/src/components/PatrolPanel.tsx'),
        evidence_artifacts=('simulation_smoke', 'host_harness_smoke', 'runtime_signal_matrix_report', 'target_environment_acceptance', 'operator_docs_review'),
        external_dependencies=('board_boundary_contract_or_verified_board_runtime',),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('patrol_state_machine', 'provider_switchable_navigation_entrypoint'),
        non_claims=('does_not_claim_external_nav2_stack_presence_when_adapter_runs_in_local_mode',),
        operator_notes=('simple_nav_provider 仍是默认主线；nav2_provider 当前是 governed local adapter runtime，默认隐藏并要求独立验收。',),
    ),
    'operator.runtime_param_commit': CapabilityRegistryEntry(
        capability_id='operator.runtime_param_commit',
        title='运行参数提交',
        domain='operator',
        implementation_status='mainline_runtime_parameter_commit_path',
        governance_stage='mainline',
        acceptance_stage='host_harness_verified',
        ui_exposure_policy='default_visible',
        frontend_maturity='mainline',
        release_note_policy='stable_mainline_claims_allowed',
        truth_source_paths=('ros2_ws/src/robot_web_bridge/robot_web_bridge/components/runtime_param_command_service.py', 'robot_frontend/src/components/ParamPanel.tsx'),
        evidence_artifacts=('host_harness_smoke', 'parameter_schema_report'),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('runtime_parameter_transaction',),
        non_claims=('does_not_claim_frontend_local_parameters_are_backend_authoritative',),
        operator_notes=('提交命令被接收不等于参数已稳定生效，必须看 lifecycleStatus 终态。',),
    ),
    'operator.voice_fixed_text': CapabilityRegistryEntry(
        capability_id='operator.voice_fixed_text',
        title='固定播报',
        domain='operator',
        implementation_status='mainline_command_with_external_audio_runtime',
        governance_stage='mainline',
        acceptance_stage='target_environment_acceptance_required_for_external_audio_claims',
        ui_exposure_policy='default_visible',
        frontend_maturity='mainline',
        release_note_policy='must_include_target_acceptance_scope',
        truth_source_paths=('ros2_ws/src/robot_web_bridge/robot_web_bridge/components/command_handlers.py', 'robot_frontend/src/components/VoicePanel.tsx'),
        evidence_artifacts=('host_harness_smoke', 'command_audit_report', 'target_environment_acceptance'),
        external_dependencies=('external_esp32_board_runtime',),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('voice_command_route',),
        non_claims=('does_not_claim_external_amplifier_output_evidence_inside_this_repo',),
        operator_notes=('播报命令在 Ubuntu 侧闭环，最终外设播出证据需看目标环境验收。',),
    ),
    'operator.snapshot_capture': CapabilityRegistryEntry(
        capability_id='operator.snapshot_capture',
        title='快照保存',
        domain='operator',
        implementation_status='mainline_snapshot_capture_path',
        governance_stage='mainline',
        acceptance_stage='host_harness_verified',
        ui_exposure_policy='default_visible',
        frontend_maturity='mainline',
        release_note_policy='stable_mainline_claims_allowed',
        truth_source_paths=('ros2_ws/src/robot_web_bridge/robot_web_bridge/components/command_handlers.py', 'robot_frontend/src/components/VisionPanel.tsx'),
        evidence_artifacts=('host_harness_smoke',),
        entry_surfaces=('frontend_api_facade',),
        runtime_claims=('snapshot_action_route',),
        non_claims=('does_not_claim_camera_target_environment_stability_from_repo_only',),
        operator_notes=('动作优先，服务 fallback 仅作为协议兼容路径。',),
    ),
    'observability.runtime_reports': CapabilityRegistryEntry(
        capability_id='observability.runtime_reports',
        title='运行观测与报告',
        domain='observability',
        implementation_status='mainline_observer_report_surface',
        governance_stage='mainline',
        acceptance_stage='release_quality_manifest_verified',
        ui_exposure_policy='default_visible',
        frontend_maturity='mainline_observability',
        release_note_policy='must_preserve_human_vs_machine_evidence_boundary',
        truth_source_paths=('ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py', 'robot_frontend/src/components/ReportSummaryPanel.tsx'),
        evidence_artifacts=('release_quality_manifest', 'runtime_signal_matrix_report'),
        entry_surfaces=('frontend_api_facade', 'bridge_observer_surface'),
        runtime_claims=('observer_only_report_surface',),
        non_claims=('human_summary_reports_must_not_be_promoted_to_machine_gate_without_registry_update',),
        operator_notes=('除 runtime_supervision 外，报告默认是 human summary，不得越权充当机器验收事实。',),
    ),
    'observability.system_replay_evidence': CapabilityRegistryEntry(
        capability_id='observability.system_replay_evidence',
        title='系统级回放证据',
        domain='observability',
        implementation_status='evidence_bundle_only',
        governance_stage='evidence_only',
        acceptance_stage='system_replay_bundle_required',
        ui_exposure_policy='default_visible',
        frontend_maturity='evidence_only',
        release_note_policy='must_not_promote_demo_replay_to_system_acceptance',
        truth_source_paths=('scripts/build_system_replay_bundle.py', 'robot_frontend/src/components/ReplayPanel.tsx'),
        evidence_artifacts=('system_replay_bundle',),
        external_dependencies=('rosbag2', 'mcap'),
        entry_surfaces=('release_reports',),
        runtime_claims=('system_replay_evidence_bundle',),
        non_claims=('frontend_json_demo_replay_is_not_system_acceptance_evidence',),
        operator_notes=('系统级 replay 与前端本地 demo replay 必须分层。',),
    ),
    'observability.standard_readonly_bridge': CapabilityRegistryEntry(
        capability_id='observability.standard_readonly_bridge',
        title='标准只读观测桥',
        domain='observability',
        implementation_status='repo_audited_readonly_proxy_runtime',
        governance_stage='experimental_gated',
        acceptance_stage='host_harness_operator_docs_and_boundary_tests_verified',
        ui_exposure_policy='hidden_by_default',
        frontend_maturity='mainline',
        release_note_policy='must_include_localhost_and_readonly_boundary_notes',
        truth_source_paths=('ros2_ws/src/robot_web_bridge/robot_web_bridge/standard_observability_contract.py', 'ros2_ws/src/robot_web_bridge/robot_web_bridge/standard_observability_bridge_launcher.py', 'ros2_ws/src/robot_web_bridge/robot_web_bridge/standard_observability_bridge_runtime.py', 'ros2_ws/src/robot_bringup/config/bridge.yaml'),
        evidence_artifacts=('host_harness_smoke', 'operator_docs_review', 'boundary_policy_test'),
        external_dependencies=(),
        entry_surfaces=('debug_observability_surface',),
        runtime_claims=('localhost_only_readonly_topic_proxy', 'no_command_forwarding', 'observer_surface_upstream_proxy'),
        non_claims=('does_not_claim_operator_command_ingress', 'does_not_claim_generic_rosbridge_write_capability'),
        operator_notes=('标准桥运行时仅监听 localhost，并只允许 ping/list_topics/subscribe/unsubscribe 这类只读客户端操作。',),
    ),
    'orchestration.fleet_adapter_boundary': CapabilityRegistryEntry(
        capability_id='orchestration.fleet_adapter_boundary',
        title='车队调度适配边界',
        domain='orchestration',
        implementation_status='single_robot_runtime_boundary_contract',
        governance_stage='mainline',
        acceptance_stage='target_environment_acceptance_required_for_external_dispatch_claims',
        ui_exposure_policy='hidden_by_default',
        frontend_maturity='mainline',
        release_note_policy='must_not_claim_scheduler_runtime_inside_repo',
        truth_source_paths=('ros2_ws/src/robot_decision/robot_decision/fleet_adapter_boundary.py', 'ros2_ws/src/robot_bringup/config/fleet_adapter.yaml'),
        evidence_artifacts=('operator_docs_review', 'target_environment_acceptance'),
        external_dependencies=('external_scheduler_or_fleet_manager',),
        entry_surfaces=('external_scheduler_boundary',),
        runtime_claims=('single_robot_runtime_boundary_contract',),
        non_claims=('does_not_claim_multi_robot_scheduler_runtime_inside_repo',),
        operator_notes=('当前仓库只提供单机器人主线；车队调度必须经外部适配边界接入。',),
    ),
}


def get_capability_entry(capability_id: str) -> CapabilityRegistryEntry:
    normalized = str(capability_id or '').strip()
    if normalized not in _CAPABILITY_REGISTRY:
        raise ValueError(f'unsupported capability_id: {capability_id!r}')
    return _CAPABILITY_REGISTRY[normalized]



def capability_registry_payload(*, domain: str | None = None) -> dict[str, dict[str, Any]]:
    normalized_domain = str(domain or '').strip()
    payload: dict[str, dict[str, Any]] = {}
    for capability_id, entry in sorted(_CAPABILITY_REGISTRY.items()):
        if normalized_domain and entry.domain != normalized_domain:
            continue
        payload[capability_id] = entry.to_dict()
    return payload
