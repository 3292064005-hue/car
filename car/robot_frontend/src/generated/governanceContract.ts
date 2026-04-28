import { z } from 'zod';

        export const capabilityRegistry = {
  "hardware.direct_driver": {
    "capabilityId": "hardware.direct_driver",
    "title": "旧 direct-driver 兼容别名",
    "domain": "hardware",
    "implementationStatus": "deprecated_compatibility_alias",
    "governanceStage": "rollback_only",
    "acceptanceStage": "not_a_claim_source_use_ros_soft_driver_or_verified_board_driver",
    "uiExposurePolicy": "hidden_by_default",
    "frontendMaturity": "deprecated",
    "releaseNotePolicy": "must_not_use_as_primary_board_execution_claim",
    "truthSourcePaths": [
      "ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_activation.py",
      "ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_adapter.py"
    ],
    "evidenceArtifacts": [],
    "externalDependencies": [],
    "entrySurfaces": [],
    "runtimeClaims": [
      "legacy_config_compatibility_alias"
    ],
    "nonClaims": [
      "does_not_define_a_primary_hardware_lane"
    ],
    "operatorNotes": [
      "direct_driver 仅作为旧配置兼容别名保留，新配置必须显式使用 ros_soft_driver 或 verified_board_driver。"
    ]
  },
  "hardware.ros_projection_only": {
    "capabilityId": "hardware.ros_projection_only",
    "title": "ROS 投影视图硬件边界",
    "domain": "hardware",
    "implementationStatus": "mainline_projection_surface",
    "governanceStage": "mainline",
    "acceptanceStage": "host_harness_verified",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "stable_mainline_claims_allowed",
    "truthSourcePaths": [
      "ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_adapter.py",
      "ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_contract.py"
    ],
    "evidenceArtifacts": [
      "host_harness_smoke"
    ],
    "externalDependencies": [],
    "entrySurfaces": [
      "frontend_api_facade",
      "bridge_observer_surface"
    ],
    "runtimeClaims": [
      "projection_surface",
      "telemetry_projection",
      "summary_contract"
    ],
    "nonClaims": [
      "does_not_claim_board_command_authority_inside_ros"
    ],
    "operatorNotes": [
      "projection-only lane 作为兼容/回滚面保留，不再是默认硬件主线。"
    ]
  },
  "hardware.ros_soft_driver": {
    "capabilityId": "hardware.ros_soft_driver",
    "title": "ROS 软驱动硬件边界",
    "domain": "hardware",
    "implementationStatus": "ros_soft_driver_no_verified_board_claim",
    "governanceStage": "experimental_gated",
    "acceptanceStage": "host_harness_or_operator_selected_real_robot_soft_driver",
    "uiExposurePolicy": "hidden_by_default",
    "frontendMaturity": "limited",
    "releaseNotePolicy": "must_include_board_execution_non_claims",
    "truthSourcePaths": [
      "ros2_ws/src/robot_direct_driver/robot_direct_driver/direct_driver_node.py",
      "ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_adapter.py",
      "ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_activation.py"
    ],
    "evidenceArtifacts": [
      "host_harness_smoke",
      "runtime_signal_matrix_report"
    ],
    "externalDependencies": [],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "ros_owned_soft_driver_loop",
      "driver_lane_summary_contract"
    ],
    "nonClaims": [
      "does_not_claim_verified_board_execution",
      "does_not_claim_target_acceptance"
    ],
    "operatorNotes": [
      "ros_soft_driver 可运行软驱动/传输循环，但不是已验板级执行闭环。"
    ]
  },
  "hardware.verified_board_driver": {
    "capabilityId": "hardware.verified_board_driver",
    "title": "已验板级驱动 lane",
    "domain": "hardware",
    "implementationStatus": "verified_board_driver_acceptance_gated",
    "governanceStage": "experimental_gated",
    "acceptanceStage": "hardware_in_loop_or_target_acceptance_required_for_board_execution_claims",
    "uiExposurePolicy": "hidden_by_default",
    "frontendMaturity": "limited",
    "releaseNotePolicy": "must_bind_activation_to_fresh_acceptance_evidence",
    "truthSourcePaths": [
      "ros2_ws/src/robot_direct_driver/robot_direct_driver/direct_driver_node.py",
      "ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_adapter.py",
      "ros2_ws/src/robot_hardware_interface/robot_hardware_interface/hardware_activation.py",
      "ros2_ws/src/robot_hardware_interface/robot_hardware_interface/standardization_target.py"
    ],
    "evidenceArtifacts": [
      "hardware_in_loop_acceptance",
      "runtime_signal_matrix_report",
      "target_environment_acceptance"
    ],
    "externalDependencies": [
      "verified_board_runtime_or_hil_bench"
    ],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "board_execution_claims_with_verified_acceptance",
      "verified_transport_ack_heartbeat_fault_contract"
    ],
    "nonClaims": [
      "does_not_claim_board_execution_when_acceptance_identity_is_stale"
    ],
    "operatorNotes": [
      "verified_board_driver 是唯一可承载板级执行声明的 lane；缺少新鲜 acceptance 时必须拒绝激活。"
    ]
  },
  "navigation.nav2_provider": {
    "capabilityId": "navigation.nav2_provider",
    "title": "隔离导航 adapter lane",
    "domain": "navigation",
    "implementationStatus": "governed_local_adapter_runtime",
    "governanceStage": "experimental_gated",
    "acceptanceStage": "simulation_host_harness_operator_docs_and_target_environment_required_for_lane_activation",
    "uiExposurePolicy": "hidden_by_default",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "must_include_backend_non_claims",
    "truthSourcePaths": [
      "ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py",
      "ros2_ws/src/robot_navigation/robot_navigation/navigation_acceptance.py",
      "ros2_ws/src/robot_nav2_adapter/robot_nav2_adapter/backend_claims.py",
      "ros2_ws/src/robot_nav2_adapter/robot_nav2_adapter/nav2_adapter_node.py",
      "docs/release_notes/2026-04-patchD.md"
    ],
    "evidenceArtifacts": [
      "simulation_smoke",
      "host_harness_smoke",
      "provider_switch_smoke",
      "operator_docs_review",
      "target_environment_acceptance",
      "external_backend_smoke"
    ],
    "externalDependencies": [],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "provider_neutral_route_execution",
      "local_adapter_path_preview",
      "local_adapter_health",
      "gated_lane_activation"
    ],
    "nonClaims": [
      "does_not_claim_external_nav2_backend_integration_when_running_local_adapter",
      "does_not_claim_nav2_planner_controller_recovery_servers_present_without_backend_integration"
    ],
    "operatorNotes": [
      "该 lane 当前是受 gate 约束的本地 adapter runtime，不应被表述为已完成外部 Nav2 后端集成。"
    ]
  },
  "navigation.simple_nav_provider": {
    "capabilityId": "navigation.simple_nav_provider",
    "title": "主线导航 provider",
    "domain": "navigation",
    "implementationStatus": "backend_integrated_mainline",
    "governanceStage": "mainline",
    "acceptanceStage": "host_harness_verified",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "stable_mainline_claims_allowed",
    "truthSourcePaths": [
      "ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py",
      "ros2_ws/src/robot_navigation/robot_navigation/navigation_node.py"
    ],
    "evidenceArtifacts": [
      "host_harness_smoke"
    ],
    "externalDependencies": [],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "route",
      "goal_pose",
      "goal_id",
      "cancel",
      "health",
      "path_preview"
    ],
    "nonClaims": [
      "does_not_claim_external_nav2_stack"
    ],
    "operatorNotes": [
      "simple_nav_provider 是默认主线与回滚基线。"
    ]
  },
  "observability.runtime_reports": {
    "capabilityId": "observability.runtime_reports",
    "title": "运行观测与报告",
    "domain": "observability",
    "implementationStatus": "mainline_observer_report_surface",
    "governanceStage": "mainline",
    "acceptanceStage": "release_quality_manifest_verified",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "mainline_observability",
    "releaseNotePolicy": "must_preserve_human_vs_machine_evidence_boundary",
    "truthSourcePaths": [
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py",
      "robot_frontend/src/components/ReportSummaryPanel.tsx"
    ],
    "evidenceArtifacts": [
      "release_quality_manifest",
      "runtime_signal_matrix_report"
    ],
    "externalDependencies": [],
    "entrySurfaces": [
      "frontend_api_facade",
      "bridge_observer_surface"
    ],
    "runtimeClaims": [
      "observer_only_report_surface"
    ],
    "nonClaims": [
      "human_summary_reports_must_not_be_promoted_to_machine_gate_without_registry_update"
    ],
    "operatorNotes": [
      "除 runtime_supervision 外，报告默认是 human summary，不得越权充当机器验收事实。"
    ]
  },
  "observability.standard_readonly_bridge": {
    "capabilityId": "observability.standard_readonly_bridge",
    "title": "标准只读观测桥",
    "domain": "observability",
    "implementationStatus": "repo_audited_readonly_proxy_runtime",
    "governanceStage": "experimental_gated",
    "acceptanceStage": "host_harness_operator_docs_and_boundary_tests_verified",
    "uiExposurePolicy": "hidden_by_default",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "must_include_localhost_and_readonly_boundary_notes",
    "truthSourcePaths": [
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/standard_observability_contract.py",
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/standard_observability_bridge_launcher.py",
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/standard_observability_bridge_runtime.py",
      "ros2_ws/src/robot_bringup/config/bridge.yaml"
    ],
    "evidenceArtifacts": [
      "host_harness_smoke",
      "operator_docs_review",
      "boundary_policy_test"
    ],
    "externalDependencies": [],
    "entrySurfaces": [
      "debug_observability_surface"
    ],
    "runtimeClaims": [
      "localhost_only_readonly_topic_proxy",
      "no_command_forwarding",
      "observer_surface_upstream_proxy"
    ],
    "nonClaims": [
      "does_not_claim_operator_command_ingress",
      "does_not_claim_generic_rosbridge_write_capability"
    ],
    "operatorNotes": [
      "标准桥运行时仅监听 localhost，并只允许 ping/list_topics/subscribe/unsubscribe 这类只读客户端操作。"
    ]
  },
  "observability.system_replay_evidence": {
    "capabilityId": "observability.system_replay_evidence",
    "title": "系统级回放证据",
    "domain": "observability",
    "implementationStatus": "evidence_bundle_only",
    "governanceStage": "evidence_only",
    "acceptanceStage": "system_replay_bundle_required",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "evidence_only",
    "releaseNotePolicy": "must_not_promote_demo_replay_to_system_acceptance",
    "truthSourcePaths": [
      "scripts/build_system_replay_bundle.py",
      "robot_frontend/src/components/ReplayPanel.tsx"
    ],
    "evidenceArtifacts": [
      "system_replay_bundle"
    ],
    "externalDependencies": [
      "rosbag2",
      "mcap"
    ],
    "entrySurfaces": [
      "release_reports"
    ],
    "runtimeClaims": [
      "system_replay_evidence_bundle"
    ],
    "nonClaims": [
      "frontend_json_demo_replay_is_not_system_acceptance_evidence"
    ],
    "operatorNotes": [
      "系统级 replay 与前端本地 demo replay 必须分层。"
    ]
  },
  "operator.mode_switch": {
    "capabilityId": "operator.mode_switch",
    "title": "模式切换",
    "domain": "operator",
    "implementationStatus": "mainline_operator_command_path",
    "governanceStage": "mainline",
    "acceptanceStage": "host_harness_verified",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "stable_mainline_claims_allowed",
    "truthSourcePaths": [
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/command_handlers.py",
      "robot_frontend/src/components/ModePanel.tsx"
    ],
    "evidenceArtifacts": [
      "host_harness_smoke"
    ],
    "externalDependencies": [],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "authoritative_write_surface_9100"
    ],
    "nonClaims": [
      "does_not_claim_board_side_mode_execution_evidence"
    ],
    "operatorNotes": [
      "9100 API facade 是唯一权威写入口。"
    ]
  },
  "operator.patrol_execution": {
    "capabilityId": "operator.patrol_execution",
    "title": "巡检执行",
    "domain": "operator",
    "implementationStatus": "mainline_orchestrator_with_experimental_navigation_lane_option",
    "governanceStage": "mainline_with_experimental_lane_isolation",
    "acceptanceStage": "simulation_host_harness_target_environment_and_operator_docs_required",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "mainline_with_experimental_lane_isolation",
    "releaseNotePolicy": "must_preserve_navigation_lane_truth",
    "truthSourcePaths": [
      "ros2_ws/src/robot_decision/robot_decision/mission_orchestrator.py",
      "ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py",
      "robot_frontend/src/components/PatrolPanel.tsx"
    ],
    "evidenceArtifacts": [
      "simulation_smoke",
      "host_harness_smoke",
      "runtime_signal_matrix_report",
      "target_environment_acceptance",
      "operator_docs_review"
    ],
    "externalDependencies": [
      "board_boundary_contract_or_verified_board_runtime"
    ],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "patrol_state_machine",
      "provider_switchable_navigation_entrypoint"
    ],
    "nonClaims": [
      "does_not_claim_external_nav2_stack_presence_when_adapter_runs_in_local_mode"
    ],
    "operatorNotes": [
      "simple_nav_provider 仍是默认主线；nav2_provider 当前是 governed local adapter runtime，默认隐藏并要求独立验收。"
    ]
  },
  "operator.runtime_param_commit": {
    "capabilityId": "operator.runtime_param_commit",
    "title": "运行参数提交",
    "domain": "operator",
    "implementationStatus": "mainline_runtime_parameter_commit_path",
    "governanceStage": "mainline",
    "acceptanceStage": "host_harness_verified",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "stable_mainline_claims_allowed",
    "truthSourcePaths": [
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/runtime_param_command_service.py",
      "robot_frontend/src/components/ParamPanel.tsx"
    ],
    "evidenceArtifacts": [
      "host_harness_smoke",
      "parameter_schema_report"
    ],
    "externalDependencies": [],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "runtime_parameter_transaction"
    ],
    "nonClaims": [
      "does_not_claim_frontend_local_parameters_are_backend_authoritative"
    ],
    "operatorNotes": [
      "提交命令被接收不等于参数已稳定生效，必须看 lifecycleStatus 终态。"
    ]
  },
  "operator.safety_recovery": {
    "capabilityId": "operator.safety_recovery",
    "title": "急停与恢复",
    "domain": "operator",
    "implementationStatus": "mainline_operator_command_path",
    "governanceStage": "mainline",
    "acceptanceStage": "target_environment_acceptance_required_for_line_level_latency_claims",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "must_include_target_acceptance_scope",
    "truthSourcePaths": [
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/command_handlers.py",
      "robot_frontend/src/components/FaultPanel.tsx"
    ],
    "evidenceArtifacts": [
      "host_harness_smoke",
      "command_audit_report",
      "target_environment_acceptance"
    ],
    "externalDependencies": [
      "board_boundary_contract_or_verified_board_runtime"
    ],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "emergency_stop_route",
      "recovery_route"
    ],
    "nonClaims": [
      "does_not_claim_hardware_line_level_estop_latency_inside_this_repo"
    ],
    "operatorNotes": [
      "安全命令允许 soft-warn 旁路，但最终裁决以后端 ACK 为准。"
    ]
  },
  "operator.snapshot_capture": {
    "capabilityId": "operator.snapshot_capture",
    "title": "快照保存",
    "domain": "operator",
    "implementationStatus": "mainline_snapshot_capture_path",
    "governanceStage": "mainline",
    "acceptanceStage": "host_harness_verified",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "stable_mainline_claims_allowed",
    "truthSourcePaths": [
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/command_handlers.py",
      "robot_frontend/src/components/VisionPanel.tsx"
    ],
    "evidenceArtifacts": [
      "host_harness_smoke"
    ],
    "externalDependencies": [],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "snapshot_action_route"
    ],
    "nonClaims": [
      "does_not_claim_camera_target_environment_stability_from_repo_only"
    ],
    "operatorNotes": [
      "动作优先，服务 fallback 仅作为协议兼容路径。"
    ]
  },
  "operator.teleop_control": {
    "capabilityId": "operator.teleop_control",
    "title": "手动遥控",
    "domain": "operator",
    "implementationStatus": "mainline_operator_command_path",
    "governanceStage": "mainline",
    "acceptanceStage": "target_environment_acceptance_required_for_board_motion_claims",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "must_include_target_acceptance_scope",
    "truthSourcePaths": [
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/command_handlers.py",
      "robot_frontend/src/components/TeleopPanel.tsx"
    ],
    "evidenceArtifacts": [
      "host_harness_smoke",
      "command_audit_report",
      "target_environment_acceptance"
    ],
    "externalDependencies": [
      "board_boundary_contract_or_verified_board_runtime"
    ],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "authoritative_write_surface_9100",
      "manual_cmd_vel_path"
    ],
    "nonClaims": [
      "does_not_claim_real_board_motion_acceptance_without_target_environment_acceptance"
    ],
    "operatorNotes": [
      "9001 observer 面必须拒绝写命令。"
    ]
  },
  "operator.voice_fixed_text": {
    "capabilityId": "operator.voice_fixed_text",
    "title": "固定播报",
    "domain": "operator",
    "implementationStatus": "mainline_command_with_external_audio_runtime",
    "governanceStage": "mainline",
    "acceptanceStage": "target_environment_acceptance_required_for_external_audio_claims",
    "uiExposurePolicy": "default_visible",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "must_include_target_acceptance_scope",
    "truthSourcePaths": [
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/command_handlers.py",
      "robot_frontend/src/components/VoicePanel.tsx"
    ],
    "evidenceArtifacts": [
      "host_harness_smoke",
      "command_audit_report",
      "target_environment_acceptance"
    ],
    "externalDependencies": [
      "external_esp32_board_runtime"
    ],
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "runtimeClaims": [
      "voice_command_route"
    ],
    "nonClaims": [
      "does_not_claim_external_amplifier_output_evidence_inside_this_repo"
    ],
    "operatorNotes": [
      "播报命令在 Ubuntu 侧闭环，最终外设播出证据需看目标环境验收。"
    ]
  },
  "orchestration.fleet_adapter_boundary": {
    "capabilityId": "orchestration.fleet_adapter_boundary",
    "title": "车队调度适配边界",
    "domain": "orchestration",
    "implementationStatus": "single_robot_runtime_boundary_contract",
    "governanceStage": "mainline",
    "acceptanceStage": "target_environment_acceptance_required_for_external_dispatch_claims",
    "uiExposurePolicy": "hidden_by_default",
    "frontendMaturity": "mainline",
    "releaseNotePolicy": "must_not_claim_scheduler_runtime_inside_repo",
    "truthSourcePaths": [
      "ros2_ws/src/robot_decision/robot_decision/fleet_adapter_boundary.py",
      "ros2_ws/src/robot_bringup/config/fleet_adapter.yaml"
    ],
    "evidenceArtifacts": [
      "operator_docs_review",
      "target_environment_acceptance"
    ],
    "externalDependencies": [
      "external_scheduler_or_fleet_manager"
    ],
    "entrySurfaces": [
      "external_scheduler_boundary"
    ],
    "runtimeClaims": [
      "single_robot_runtime_boundary_contract"
    ],
    "nonClaims": [
      "does_not_claim_multi_robot_scheduler_runtime_inside_repo"
    ],
    "operatorNotes": [
      "当前仓库只提供单机器人主线；车队调度必须经外部适配边界接入。"
    ]
  }
} as const;
        export const laneRegistry = {
  "navigation.simple_nav_provider": {
    "laneId": "navigation.simple_nav_provider",
    "capabilityId": "navigation.simple_nav_provider",
    "domain": "navigation",
    "owner": "robot_navigation",
    "packageName": "robot_navigation",
    "executable": "navigation_node",
    "childFactory": "robot_navigation.navigation_node:RobotNavigationNode",
    "activationDecision": "activate",
    "rollbackPolicy": "baseline_runtime_remains_default",
    "evidenceRequired": [
      "host_harness_smoke"
    ],
    "upgradeCondition": "mainline_baseline_provider_already_supported",
    "description": "Baseline waypoint navigation runtime hosted in robot_navigation.",
    "visibility": "public",
    "lifecycleStage": "mainline",
    "defaultSurfaceExposure": "default_visible",
    "retentionCondition": "baseline_navigation_provider_required_for_mainline",
    "exitCondition": "only_replaced_by_new_mainline_navigation_provider"
  },
  "navigation.nav2_provider": {
    "laneId": "navigation.nav2_provider",
    "capabilityId": "navigation.nav2_provider",
    "domain": "navigation",
    "owner": "robot_nav2_adapter",
    "packageName": "robot_nav2_adapter",
    "executable": "nav2_adapter_node",
    "childFactory": "robot_nav2_adapter.nav2_adapter_node:Nav2AdapterNode",
    "activationDecision": "activate",
    "rollbackPolicy": "switch_provider_name_back_to_simple_nav_provider",
    "evidenceRequired": [
      "simulation_smoke",
      "host_harness_smoke",
      "provider_switch_smoke",
      "operator_docs_review",
      "target_environment_acceptance",
      "external_backend_smoke"
    ],
    "upgradeCondition": "adapter lane package installed and gate artifacts passing; stronger external-backend claims require backend integration evidence",
    "description": "Isolated local adapter backend lane with optional external backend contract; default in-package runtime remains the governed local adapter backend.",
    "visibility": "experimental",
    "lifecycleStage": "experimental",
    "defaultSurfaceExposure": "hidden_by_default",
    "retentionCondition": "keep_until_external_backend_integration_and_acceptance_are_verified",
    "exitCondition": "promote_only_after_external_backend_smoke_and_target_environment_acceptance_are_verified"
  },
  "hardware.ros_projection_only": {
    "laneId": "hardware.ros_projection_only",
    "capabilityId": "hardware.ros_projection_only",
    "domain": "hardware",
    "owner": "robot_hardware_interface",
    "packageName": "robot_hardware_interface",
    "executable": "hardware_interface_node",
    "childFactory": "robot_hardware_interface.hardware_interface_node:HardwareInterfaceNode",
    "activationDecision": "activate",
    "rollbackPolicy": "mainline_default_compatibility_surface",
    "evidenceRequired": [
      "host_harness_smoke"
    ],
    "upgradeCondition": "mainline_projection_surface_already_supported",
    "description": "Default ROS projection-only hardware compatibility surface.",
    "visibility": "public",
    "lifecycleStage": "mainline",
    "defaultSurfaceExposure": "default_visible",
    "retentionCondition": "mainline_projection_surface_required",
    "exitCondition": "only_removed_when_board_authority_is_re-architected"
  },
  "hardware.ros_soft_driver": {
    "laneId": "hardware.ros_soft_driver",
    "capabilityId": "hardware.ros_soft_driver",
    "domain": "hardware",
    "owner": "robot_direct_driver",
    "packageName": "robot_direct_driver",
    "executable": "direct_driver_node",
    "childFactory": "robot_direct_driver.direct_driver_node:DirectDriverNode",
    "activationDecision": "activate",
    "rollbackPolicy": "switch_compatibility_surface_role_to_ros_projection_only",
    "evidenceRequired": [
      "host_harness_smoke",
      "runtime_signal_matrix_report"
    ],
    "upgradeCondition": "explicit ros_soft_driver profile selected; no board-execution claim may be made without verified_board_driver evidence",
    "description": "ROS-owned soft driver lane. It may run the driver transport loop but is not allowed to claim verified board execution.",
    "visibility": "experimental",
    "lifecycleStage": "experimental",
    "defaultSurfaceExposure": "hidden_by_default",
    "retentionCondition": "keep_as_compatibility_lane_until_verified_board_driver_or_ros2_control_lane_replaces_it",
    "exitCondition": "remove_only_after_verified_board_driver_migration_and_rollback_window_close"
  },
  "hardware.verified_board_driver": {
    "laneId": "hardware.verified_board_driver",
    "capabilityId": "hardware.verified_board_driver",
    "domain": "hardware",
    "owner": "robot_direct_driver",
    "packageName": "robot_direct_driver",
    "executable": "direct_driver_node",
    "childFactory": "robot_direct_driver.direct_driver_node:DirectDriverNode",
    "activationDecision": "activate",
    "rollbackPolicy": "fall_back_to_ros_soft_driver_or_ros_projection_only_by_explicit_profile_change",
    "evidenceRequired": [
      "hardware_in_loop_acceptance",
      "runtime_signal_matrix_report",
      "target_environment_acceptance"
    ],
    "upgradeCondition": "fresh HIL or target acceptance artifact bound to current source/config identity",
    "description": "Verified board-driver lane. Board-execution claims are allowed only after activation evidence passes identity-bound acceptance checks.",
    "visibility": "experimental",
    "lifecycleStage": "experimental",
    "defaultSurfaceExposure": "hidden_by_default",
    "retentionCondition": "keep_separate_until_ros2_control_system_interface_lane_is_ready",
    "exitCondition": "promote_only_after_ros2_control_hardware_plugin_and_target_acceptance_close"
  },
  "hardware.direct_driver": {
    "laneId": "hardware.direct_driver",
    "capabilityId": "hardware.direct_driver",
    "domain": "hardware",
    "owner": "robot_direct_driver",
    "packageName": "robot_direct_driver",
    "executable": "direct_driver_node",
    "childFactory": "robot_direct_driver.direct_driver_node:DirectDriverNode",
    "activationDecision": "rollback_only",
    "rollbackPolicy": "legacy alias only; configure ros_soft_driver or verified_board_driver explicitly",
    "evidenceRequired": [],
    "upgradeCondition": "deprecated compatibility alias, not a primary role",
    "description": "Deprecated compatibility alias retained for old configs; new configs must use ros_soft_driver or verified_board_driver.",
    "visibility": "experimental",
    "lifecycleStage": "rollback_only",
    "defaultSurfaceExposure": "hidden_by_default",
    "retentionCondition": "retain_until_legacy_direct_driver_configs_are_migrated",
    "exitCondition": "remove_after_legacy_config_window"
  },
  "bridge_runtime.split_runtime": {
    "laneId": "bridge_runtime.split_runtime",
    "capabilityId": null,
    "domain": "bridge_runtime",
    "owner": "robot_bridge",
    "packageName": "robot_bridge",
    "executable": "bridge_transport_node",
    "childFactory": "robot_bridge.bridge_transport_node:BridgeTransportNode",
    "activationDecision": "activate",
    "rollbackPolicy": "fall_back_to_legacy_monolith_only_via_explicit_rollback_gate",
    "evidenceRequired": [
      "runtime_smoke"
    ],
    "upgradeCondition": "mainline_default_runtime",
    "description": "Mainline split bridge runtime topology.",
    "visibility": "public",
    "lifecycleStage": "mainline",
    "defaultSurfaceExposure": "default_visible",
    "retentionCondition": "mainline_bridge_runtime_required",
    "exitCondition": "only_replaced_by_new_mainline_bridge_runtime"
  },
  "bridge_runtime.legacy_monolith": {
    "laneId": "bridge_runtime.legacy_monolith",
    "capabilityId": null,
    "domain": "bridge_runtime",
    "owner": "robot_bridge",
    "packageName": "robot_bridge",
    "executable": "bridge_node",
    "childFactory": "robot_bridge.bridge_node:BridgeNode",
    "activationDecision": "rollback_only",
    "rollbackPolicy": "must_be_explicitly_enabled_by_allow_legacy_bridge_runtime",
    "evidenceRequired": [
      "legacy_runtime_smoke"
    ],
    "upgradeCondition": "kept_only_for_controlled_rollback",
    "description": "Legacy monolithic bridge runtime kept behind an explicit rollback gate.",
    "visibility": "experimental",
    "lifecycleStage": "rollback_only",
    "defaultSurfaceExposure": "hidden_by_default",
    "retentionCondition": "retain_only_until_split_runtime_rollback_window_expires",
    "exitCondition": "remove_after_controlled_rollback_window_and_release_audit_close"
  }
} as const;
        export const signalRegistry = {
  "topics": {
    "/robot/lifecycle_manager/status": {
      "kind": "topic",
      "producer": "robot_lifecycle_manager",
      "runtimeConsumers": [
        "robot_monitor"
      ],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "startup_barrier"
      ],
      "ackOwners": [],
      "notes": "Lifecycle status is consumed at runtime and surfaced in evidence/reporting.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "/robot/lifecycle_manager/ready": {
      "kind": "topic",
      "producer": "robot_lifecycle_manager",
      "runtimeConsumers": [
        "startup_barrier"
      ],
      "uiConsumers": [],
      "evidenceConsumers": [],
      "ackOwners": [],
      "notes": "Lifecycle readiness gates startup barrier only.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "/robot/bridge/summary": {
      "kind": "topic",
      "producer": "robot_bridge_or_robot_direct_driver",
      "runtimeConsumers": [
        "robot_monitor",
        "robot_web_bridge"
      ],
      "uiConsumers": [],
      "evidenceConsumers": [
        "probe_real_board_acceptance"
      ],
      "ackOwners": [],
      "notes": "Bridge summary feeds readiness, staleness and evidence logic.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "/robot/bridge/transport_stats": {
      "kind": "topic",
      "producer": "robot_bridge",
      "runtimeConsumers": [
        "robot_web_bridge"
      ],
      "uiConsumers": [],
      "evidenceConsumers": [],
      "ackOwners": [],
      "notes": "Detailed transport statistics are optional runtime telemetry.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "/robot/decision/summary": {
      "kind": "topic",
      "producer": "robot_decision",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_voice"
      ],
      "uiConsumers": [],
      "evidenceConsumers": [
        "startup_barrier"
      ],
      "ackOwners": [],
      "notes": "Decision summary is the authoritative mode/task projection.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "/robot/runtime/supervision": {
      "kind": "topic",
      "producer": "robot_monitor",
      "runtimeConsumers": [
        "robot_decision",
        "robot_web_bridge"
      ],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "preflight_environment_check"
      ],
      "ackOwners": [],
      "notes": "Runtime supervision is both runtime-consumed and operator-visible.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "/robot/web_bridge/ready": {
      "kind": "topic",
      "producer": "robot_web_bridge",
      "runtimeConsumers": [
        "startup_barrier"
      ],
      "uiConsumers": [],
      "evidenceConsumers": [
        "run_integrated_frontend_bridge_smoke"
      ],
      "ackOwners": [],
      "notes": "Gateway-ready topic remains a startup gate and smoke-evidence signal.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "/robot/control/summary": {
      "kind": "topic",
      "producer": "robot_control",
      "runtimeConsumers": [
        "robot_monitor"
      ],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_control_summary_report"
      ],
      "ackOwners": [],
      "notes": "Control summary governs runtime/operator visibility of arbitration outcomes.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "/robot/monitor/summary": {
      "kind": "topic",
      "producer": "robot_monitor",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_monitor_summary_report"
      ],
      "ackOwners": [],
      "notes": "Monitor summary is observability-only telemetry.",
      "evidenceLayer": "human_summary",
      "machineEvidenceAllowed": false
    },
    "/robot/monitor/diagnostics_json": {
      "kind": "topic",
      "producer": "robot_monitor",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_monitor_diagnostics_report"
      ],
      "ackOwners": [],
      "notes": "Diagnostics export is evidence/UI only.",
      "evidenceLayer": "human_summary",
      "machineEvidenceAllowed": false
    },
    "/robot/navigation/status": {
      "kind": "topic",
      "producer": "robot_navigation_or_robot_nav2_adapter",
      "runtimeConsumers": [
        "robot_decision",
        "robot_web_bridge"
      ],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_runtime_signal_matrix_report"
      ],
      "ackOwners": [],
      "notes": "Navigation lifecycle/status surface shared by both provider lanes.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "/robot/navigation/path": {
      "kind": "topic",
      "producer": "robot_navigation_or_robot_nav2_adapter",
      "runtimeConsumers": [
        "robot_web_bridge"
      ],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_runtime_signal_matrix_report"
      ],
      "ackOwners": [],
      "notes": "Navigation path preview surface shared by both provider lanes.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "/robot/hardware_interface/summary": {
      "kind": "topic",
      "producer": "robot_hardware_interface_or_robot_direct_driver",
      "runtimeConsumers": [
        "robot_web_bridge"
      ],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_runtime_signal_matrix_report"
      ],
      "ackOwners": [],
      "notes": "Hardware boundary summary shared by projection and direct-driver lanes.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    }
  },
  "commands": {
    "set_mode": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_decision"
      ],
      "uiConsumers": [
        "ModePanel"
      ],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_decision"
      ],
      "notes": "Mode transitions are authorized by robot_decision.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "teleop_cmd": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_control"
      ],
      "uiConsumers": [
        "TeleopPanel"
      ],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_control"
      ],
      "notes": "Teleop commands are ultimately accepted by control arbitration.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "stop_now": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_control"
      ],
      "uiConsumers": [
        "TeleopPanel"
      ],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_control"
      ],
      "notes": "Stop-now is a control-owned command.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "estop": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_control"
      ],
      "uiConsumers": [
        "FaultPanel"
      ],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_control"
      ],
      "notes": "Emergency stop is latched by control.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "resume_from_safe_stop": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_decision"
      ],
      "uiConsumers": [
        "FaultPanel"
      ],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_decision"
      ],
      "notes": "Safe-stop recovery is governed by decision policy.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "start_patrol": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_decision",
        "robot_navigation_or_robot_nav2_adapter"
      ],
      "uiConsumers": [
        "PatrolPanel"
      ],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_decision"
      ],
      "notes": "Decision orchestrates patrol start and navigation intent emission.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "pause_patrol": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_decision"
      ],
      "uiConsumers": [
        "PatrolPanel"
      ],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_decision"
      ],
      "notes": "Patrol pause is coordinated by decision.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "stop_patrol": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_decision"
      ],
      "uiConsumers": [
        "PatrolPanel"
      ],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_decision"
      ],
      "notes": "Patrol stop is coordinated by decision.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "apply_param_draft": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_control",
        "robot_decision",
        "robot_monitor"
      ],
      "uiConsumers": [
        "ParamPanel"
      ],
      "evidenceConsumers": [
        "render_parameter_schema_report"
      ],
      "ackOwners": [
        "robot_control",
        "robot_decision",
        "robot_monitor"
      ],
      "notes": "Runtime parameter commits aggregate authoritative consumer ACKs only.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "apply_param_profile": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_control",
        "robot_decision",
        "robot_monitor"
      ],
      "uiConsumers": [
        "ParamPanel"
      ],
      "evidenceConsumers": [
        "render_parameter_schema_report"
      ],
      "ackOwners": [
        "robot_control",
        "robot_decision",
        "robot_monitor"
      ],
      "notes": "Runtime parameter profiles aggregate authoritative consumer ACKs only.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "speak_fixed_text": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_voice"
      ],
      "uiConsumers": [
        "VoicePanel"
      ],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_voice"
      ],
      "notes": "Voice subsystem is authoritative for canned speech.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "reset_fault": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_decision",
        "robot_control"
      ],
      "uiConsumers": [
        "FaultPanel"
      ],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_decision",
        "robot_control"
      ],
      "notes": "Fault reset requires coordinated decision/control handling.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    },
    "save_snapshot": {
      "kind": "command",
      "producer": "robot_frontend_or_api_server",
      "runtimeConsumers": [
        "robot_web_bridge",
        "robot_vision"
      ],
      "uiConsumers": [],
      "evidenceConsumers": [
        "render_command_audit_report"
      ],
      "ackOwners": [
        "robot_vision"
      ],
      "notes": "Snapshot capture is handled by the vision subsystem.",
      "evidenceLayer": "command_audit",
      "machineEvidenceAllowed": true
    }
  },
  "runtimeParameters": {
    "maxLinearSpeed": {
      "kind": "runtime_parameter",
      "producer": "robot_frontend",
      "scope": "backend_authoritative",
      "runtimeConsumers": [
        "robot_control",
        "robot_decision"
      ],
      "uiConsumers": [],
      "evidenceConsumers": [
        "render_parameter_schema_report"
      ],
      "ackOwners": [
        "robot_control",
        "robot_decision"
      ],
      "notes": "control and decision consume the authoritative linear speed limit.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "maxAngularSpeed": {
      "kind": "runtime_parameter",
      "producer": "robot_frontend",
      "scope": "backend_authoritative",
      "runtimeConsumers": [
        "robot_control",
        "robot_decision"
      ],
      "uiConsumers": [],
      "evidenceConsumers": [
        "render_parameter_schema_report"
      ],
      "ackOwners": [
        "robot_control",
        "robot_decision"
      ],
      "notes": "control and decision consume the authoritative angular speed limit.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "teleopStep": {
      "kind": "runtime_parameter",
      "producer": "robot_frontend",
      "scope": "frontend_local",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ParamPanel"
      ],
      "evidenceConsumers": [
        "render_parameter_schema_report"
      ],
      "ackOwners": [],
      "notes": "browser-local teleop increment used by operator UI only.",
      "evidenceLayer": "ui_local_only",
      "machineEvidenceAllowed": false
    },
    "trackOffsetDeadband": {
      "kind": "runtime_parameter",
      "producer": "robot_frontend",
      "scope": "backend_authoritative",
      "runtimeConsumers": [
        "robot_decision"
      ],
      "uiConsumers": [],
      "evidenceConsumers": [
        "render_parameter_schema_report"
      ],
      "ackOwners": [
        "robot_decision"
      ],
      "notes": "decision tracking controller consumes the authoritative offset deadband.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "lowPowerThreshold": {
      "kind": "runtime_parameter",
      "producer": "robot_frontend",
      "scope": "backend_authoritative",
      "runtimeConsumers": [
        "robot_monitor"
      ],
      "uiConsumers": [],
      "evidenceConsumers": [
        "render_parameter_schema_report"
      ],
      "ackOwners": [
        "robot_monitor"
      ],
      "notes": "monitor readiness and low-power supervision consume the authoritative threshold.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    },
    "reconnectTimeoutMs": {
      "kind": "runtime_parameter",
      "producer": "robot_frontend",
      "scope": "frontend_local",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ParamPanel"
      ],
      "evidenceConsumers": [
        "render_parameter_schema_report"
      ],
      "ackOwners": [],
      "notes": "browser-local reconnect/watchdog timeout used by frontend transport tick only.",
      "evidenceLayer": "ui_local_only",
      "machineEvidenceAllowed": false
    }
  },
  "reports": {
    "control_summary": {
      "kind": "report",
      "producer": "render_control_summary_report",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_acceptance_report",
        "render_release_quality_manifest"
      ],
      "ackOwners": [],
      "notes": "Control summary report is exported for operator review and release evidence.",
      "evidenceLayer": "human_summary",
      "machineEvidenceAllowed": false
    },
    "monitor_summary": {
      "kind": "report",
      "producer": "render_monitor_summary_report",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_acceptance_report",
        "render_release_quality_manifest"
      ],
      "ackOwners": [],
      "notes": "Monitor summary report remains evidence/UI only.",
      "evidenceLayer": "human_summary",
      "machineEvidenceAllowed": false
    },
    "monitor_diagnostics": {
      "kind": "report",
      "producer": "render_monitor_diagnostics_report",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_acceptance_report"
      ],
      "ackOwners": [],
      "notes": "Diagnostics report is evidence/UI only.",
      "evidenceLayer": "human_summary",
      "machineEvidenceAllowed": false
    },
    "localization_summary": {
      "kind": "report",
      "producer": "render_runtime_signal_matrix_report",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_release_quality_manifest"
      ],
      "ackOwners": [],
      "notes": "Localization summary is exported from runtime snapshots.",
      "evidenceLayer": "human_summary",
      "machineEvidenceAllowed": false
    },
    "hardware_interface_summary": {
      "kind": "report",
      "producer": "render_runtime_signal_matrix_report",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_release_quality_manifest"
      ],
      "ackOwners": [],
      "notes": "Hardware summary is exported from runtime snapshots.",
      "evidenceLayer": "human_summary",
      "machineEvidenceAllowed": false
    },
    "navigation_status": {
      "kind": "report",
      "producer": "render_runtime_signal_matrix_report",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_release_quality_manifest"
      ],
      "ackOwners": [],
      "notes": "Navigation status report is exported from runtime snapshots.",
      "evidenceLayer": "human_summary",
      "machineEvidenceAllowed": false
    },
    "navigation_path": {
      "kind": "report",
      "producer": "render_runtime_signal_matrix_report",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_release_quality_manifest"
      ],
      "ackOwners": [],
      "notes": "Navigation path report is exported from runtime snapshots.",
      "evidenceLayer": "human_summary",
      "machineEvidenceAllowed": false
    },
    "runtime_supervision": {
      "kind": "report",
      "producer": "render_runtime_signal_matrix_report",
      "runtimeConsumers": [],
      "uiConsumers": [
        "ReportSummaryPanel"
      ],
      "evidenceConsumers": [
        "render_release_quality_manifest",
        "render_acceptance_report"
      ],
      "ackOwners": [],
      "notes": "Runtime supervision report is consumed by acceptance/release gates.",
      "evidenceLayer": "machine_gate",
      "machineEvidenceAllowed": true
    }
  },
  "validationErrors": []
} as const;
        export const featureAdmissionRegistry = {
  "operator.mode_switch": {
    "featureId": "operator.mode_switch",
    "capabilityIds": [
      "operator.mode_switch"
    ],
    "title": "模式切换",
    "maturity": "mainline",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "commands": [
      "set_mode"
    ],
    "authoritativeNodes": [
      "robot_decision"
    ],
    "runtimeProducers": [
      "robot_api_server",
      "robot_web_bridge",
      "/robot/set_mode"
    ],
    "runtimeConsumers": [
      "robot_decision",
      "robot_control"
    ],
    "uiConsumers": [
      "ModePanel",
      "TeleopPanel"
    ],
    "configPaths": [
      "ros2_ws/src/robot_bringup/config/launch_profiles.yaml",
      "robot_frontend/.env.example"
    ],
    "verificationTargets": [
      "test_governance_registry.py",
      "test_frontend_authoritative_write_path.py",
      "scripts/check_contract_consistency.py"
    ],
    "acceptanceArtifacts": [
      "host_harness_smoke"
    ],
    "rollbackPaths": [
      "set_mode:IDLE",
      "backend-rollback surface"
    ],
    "externalDependencies": [],
    "nonClaims": [
      "does_not_claim_board_side_mode_execution_evidence"
    ],
    "operatorNotes": [
      "9100 API facade 是唯一权威写入口。"
    ]
  },
  "operator.teleop_control": {
    "featureId": "operator.teleop_control",
    "capabilityIds": [
      "operator.teleop_control"
    ],
    "title": "手动遥控",
    "maturity": "mainline",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "commands": [
      "teleop_cmd",
      "stop_now"
    ],
    "authoritativeNodes": [
      "robot_control"
    ],
    "runtimeProducers": [
      "robot_api_server",
      "robot_web_bridge",
      "/robot/manual/cmd_vel"
    ],
    "runtimeConsumers": [
      "robot_control",
      "robot_bridge"
    ],
    "uiConsumers": [
      "TeleopPanel"
    ],
    "configPaths": [
      "ros2_ws/src/robot_bringup/config/launch_profiles.yaml",
      "docs/protocols/bridge-contract.md"
    ],
    "verificationTargets": [
      "test_governance_registry.py",
      "test_frontend_authoritative_write_path.py",
      "scripts/check_feature_admission.py"
    ],
    "acceptanceArtifacts": [
      "host_harness_smoke",
      "command_audit_report",
      "target_environment_acceptance"
    ],
    "rollbackPaths": [
      "stop_now",
      "disable frontend operator session"
    ],
    "externalDependencies": [
      "board_boundary_contract_or_verified_board_runtime"
    ],
    "nonClaims": [
      "does_not_claim_real_board_motion_acceptance_without_target_environment_acceptance"
    ],
    "operatorNotes": [
      "9001 observer 面必须拒绝写命令。"
    ]
  },
  "operator.safety_recovery": {
    "featureId": "operator.safety_recovery",
    "capabilityIds": [
      "operator.safety_recovery"
    ],
    "title": "急停与恢复",
    "maturity": "mainline",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "commands": [
      "estop",
      "resume_from_safe_stop",
      "reset_fault"
    ],
    "authoritativeNodes": [
      "robot_control",
      "robot_decision"
    ],
    "runtimeProducers": [
      "robot_api_server",
      "robot_web_bridge",
      "/robot/set_mode",
      "/robot/reset_fault"
    ],
    "runtimeConsumers": [
      "robot_control",
      "robot_decision"
    ],
    "uiConsumers": [
      "FaultPanel"
    ],
    "configPaths": [
      "docs/state-machine.md",
      "docs/protocols/bridge-contract.md"
    ],
    "verificationTargets": [
      "test_governance_registry.py",
      "scripts/check_contract_consistency.py",
      "scripts/check_feature_admission.py"
    ],
    "acceptanceArtifacts": [
      "host_harness_smoke",
      "command_audit_report",
      "target_environment_acceptance"
    ],
    "rollbackPaths": [
      "estop latch remains available",
      "backend-rollback surface"
    ],
    "externalDependencies": [
      "board_boundary_contract_or_verified_board_runtime"
    ],
    "nonClaims": [
      "does_not_claim_hardware_line_level_estop_latency_inside_this_repo"
    ],
    "operatorNotes": [
      "安全命令允许 soft-warn 旁路，但最终裁决以后端 ACK 为准。"
    ]
  },
  "operator.patrol_execution": {
    "featureId": "operator.patrol_execution",
    "capabilityIds": [
      "operator.patrol_execution",
      "navigation.simple_nav_provider",
      "navigation.nav2_provider"
    ],
    "title": "巡检执行",
    "maturity": "mainline_with_experimental_lane_isolation",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "commands": [
      "start_patrol",
      "pause_patrol",
      "stop_patrol"
    ],
    "authoritativeNodes": [
      "robot_decision",
      "robot_navigation"
    ],
    "runtimeProducers": [
      "robot_api_server",
      "robot_web_bridge",
      "robot_decision",
      "robot_navigation"
    ],
    "runtimeConsumers": [
      "robot_navigation",
      "robot_web_bridge",
      "robot_bridge"
    ],
    "uiConsumers": [
      "PatrolPanel"
    ],
    "configPaths": [
      "ros2_ws/src/robot_bringup/config/navigation.yaml",
      "ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py"
    ],
    "verificationTargets": [
      "test_governance_registry.py",
      "scripts/check_feature_admission.py",
      "test_reporting_scripts.py"
    ],
    "acceptanceArtifacts": [
      "simulation_smoke",
      "host_harness_smoke",
      "runtime_signal_matrix_report",
      "target_environment_acceptance",
      "operator_docs_review",
      "external_backend_smoke"
    ],
    "rollbackPaths": [
      "switch provider to simple_nav_provider",
      "stop_patrol",
      "backend-rollback surface"
    ],
    "externalDependencies": [
      "board_boundary_contract_or_verified_board_runtime"
    ],
    "nonClaims": [
      "does_not_claim_external_nav2_stack_presence_when_adapter_runs_in_local_mode"
    ],
    "operatorNotes": [
      "simple_nav_provider 仍是默认主线；nav2_provider 当前是 governed local adapter runtime，默认隐藏并要求独立验收。"
    ]
  },
  "operator.runtime_param_commit": {
    "featureId": "operator.runtime_param_commit",
    "capabilityIds": [
      "operator.runtime_param_commit"
    ],
    "title": "运行参数提交",
    "maturity": "mainline",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "commands": [
      "apply_param_draft",
      "apply_param_profile"
    ],
    "authoritativeNodes": [
      "robot_control",
      "robot_decision",
      "robot_monitor"
    ],
    "runtimeProducers": [
      "robot_api_server",
      "robot_web_bridge",
      "runtime_param_coordinator"
    ],
    "runtimeConsumers": [
      "robot_control",
      "robot_decision",
      "robot_monitor"
    ],
    "uiConsumers": [
      "ParamPanel"
    ],
    "configPaths": [
      "ros2_ws/src/robot_bringup/config/*.yaml",
      "ros2_ws/src/robot_contracts/robot_contracts/runtime_parameters.py"
    ],
    "verificationTargets": [
      "scripts/validate_configs.py",
      "scripts/check_feature_admission.py",
      "test_governance_registry.py"
    ],
    "acceptanceArtifacts": [
      "host_harness_smoke",
      "parameter_schema_report"
    ],
    "rollbackPaths": [
      "apply_param_profile:last_known_good"
    ],
    "externalDependencies": [],
    "nonClaims": [
      "does_not_claim_frontend_local_parameters_are_backend_authoritative"
    ],
    "operatorNotes": [
      "提交命令被接收不等于参数已稳定生效，必须看 lifecycleStatus 终态。"
    ]
  },
  "operator.voice_fixed_text": {
    "featureId": "operator.voice_fixed_text",
    "capabilityIds": [
      "operator.voice_fixed_text"
    ],
    "title": "固定播报",
    "maturity": "mainline",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "commands": [
      "speak_fixed_text"
    ],
    "authoritativeNodes": [
      "robot_voice"
    ],
    "runtimeProducers": [
      "robot_api_server",
      "robot_web_bridge",
      "/robot/speak_req"
    ],
    "runtimeConsumers": [
      "robot_voice",
      "/robot/speak_tx"
    ],
    "uiConsumers": [
      "VoicePanel"
    ],
    "configPaths": [
      "docs/protocols/bridge-contract.md"
    ],
    "verificationTargets": [
      "scripts/check_feature_admission.py",
      "test_governance_registry.py"
    ],
    "acceptanceArtifacts": [
      "host_harness_smoke",
      "command_audit_report",
      "target_environment_acceptance"
    ],
    "rollbackPaths": [
      "disable voice ingress route"
    ],
    "externalDependencies": [
      "external_esp32_board_runtime"
    ],
    "nonClaims": [
      "does_not_claim_external_amplifier_output_evidence_inside_this_repo"
    ],
    "operatorNotes": [
      "播报命令在 Ubuntu 侧闭环，最终外设播出证据需看目标环境验收。"
    ]
  },
  "operator.snapshot_capture": {
    "featureId": "operator.snapshot_capture",
    "capabilityIds": [
      "operator.snapshot_capture"
    ],
    "title": "快照保存",
    "maturity": "mainline",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "commands": [
      "save_snapshot"
    ],
    "authoritativeNodes": [
      "robot_vision"
    ],
    "runtimeProducers": [
      "robot_api_server",
      "robot_web_bridge",
      "/robot/actions/save_snapshot"
    ],
    "runtimeConsumers": [
      "robot_vision"
    ],
    "uiConsumers": [
      "VisionPanel",
      "FaultPanel"
    ],
    "configPaths": [
      "docs/protocols/bridge-contract.md"
    ],
    "verificationTargets": [
      "scripts/check_feature_admission.py",
      "test_governance_registry.py"
    ],
    "acceptanceArtifacts": [
      "host_harness_smoke"
    ],
    "rollbackPaths": [
      "fallback to service /robot/save_snapshot when action unavailable"
    ],
    "externalDependencies": [],
    "nonClaims": [
      "does_not_claim_camera_target_environment_stability_from_repo_only"
    ],
    "operatorNotes": [
      "动作优先，服务 fallback 仅作为协议兼容路径。"
    ]
  },
  "observability.runtime_reports": {
    "featureId": "observability.runtime_reports",
    "capabilityIds": [
      "observability.runtime_reports"
    ],
    "title": "运行观测与报告",
    "maturity": "mainline_observability",
    "entrySurfaces": [
      "frontend_api_facade",
      "bridge_observer_surface"
    ],
    "commands": [],
    "authoritativeNodes": [
      "robot_monitor"
    ],
    "runtimeProducers": [
      "robot_monitor",
      "scripts/render_*_report.py"
    ],
    "runtimeConsumers": [
      "robot_web_bridge",
      "startup_barrier"
    ],
    "uiConsumers": [
      "ReportSummaryPanel"
    ],
    "configPaths": [
      "docs/governance/capability-ownership.md",
      "ros2_ws/src/robot_contracts/robot_contracts/signal_ownership.py"
    ],
    "verificationTargets": [
      "scripts/check_evidence_layering.py",
      "test_reporting_scripts.py",
      "test_governance_registry.py"
    ],
    "acceptanceArtifacts": [
      "release_quality_manifest",
      "runtime_signal_matrix_report"
    ],
    "rollbackPaths": [
      "disable observer-only report surfacing"
    ],
    "externalDependencies": [],
    "nonClaims": [
      "human_summary_reports_must_not_be_promoted_to_machine_gate_without_registry_update"
    ],
    "operatorNotes": [
      "除 runtime_supervision 外，报告默认是 human summary，不得越权充当机器验收事实。"
    ]
  },
  "observability.system_replay_evidence": {
    "featureId": "observability.system_replay_evidence",
    "capabilityIds": [
      "observability.system_replay_evidence"
    ],
    "title": "系统级回放证据",
    "maturity": "evidence_only",
    "entrySurfaces": [
      "release_reports"
    ],
    "commands": [],
    "authoritativeNodes": [
      "rosbag2_or_mcap_capture"
    ],
    "runtimeProducers": [
      "robot_monitor",
      "build_system_replay_bundle.py",
      "render_system_replay_report.py"
    ],
    "runtimeConsumers": [
      "release_quality_manifest",
      "acceptance_review"
    ],
    "uiConsumers": [
      "ReplayPanel"
    ],
    "configPaths": [
      "docs/governance/replay-evidence.md",
      "ros2_ws/src/robot_bringup/config/monitor.yaml"
    ],
    "verificationTargets": [
      "test_reporting_scripts.py",
      "scripts/check_feature_admission.py"
    ],
    "acceptanceArtifacts": [
      "system_replay_bundle"
    ],
    "rollbackPaths": [
      "retain_frontend_local_replay_without_claiming_system_evidence"
    ],
    "externalDependencies": [
      "rosbag2",
      "mcap"
    ],
    "nonClaims": [
      "frontend_json_demo_replay_is_not_system_acceptance_evidence"
    ],
    "operatorNotes": [
      "系统级 replay 与前端本地 demo replay 必须分层。"
    ]
  }
} as const;
        export const commandRouteRegistry = {
  "apply_param_draft": {
    "commandType": "apply_param_draft",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_apply_param_draft",
    "targetNodes": [
      "runtime_param_coordinator",
      "robot_control",
      "robot_decision",
      "robot_monitor"
    ],
    "timeoutBudgetMs": 6000,
    "fallbackPaths": [],
    "denyConditions": [
      "readonly_session",
      "observer_surface",
      "empty_runtime_param_patch"
    ],
    "rollbackPaths": [
      "apply_param_profile:last_known_good"
    ],
    "allowedModes": [
      "IDLE",
      "MANUAL",
      "PATROL",
      "TRACK"
    ],
    "targetMode": null,
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": []
  },
  "apply_param_profile": {
    "commandType": "apply_param_profile",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_apply_param_profile",
    "targetNodes": [
      "runtime_param_coordinator",
      "robot_control",
      "robot_decision",
      "robot_monitor"
    ],
    "timeoutBudgetMs": 6000,
    "fallbackPaths": [],
    "denyConditions": [
      "readonly_session",
      "observer_surface",
      "unknown_runtime_profile"
    ],
    "rollbackPaths": [
      "apply_param_profile:last_known_good"
    ],
    "allowedModes": [
      "IDLE",
      "MANUAL"
    ],
    "targetMode": null,
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": []
  },
  "estop": {
    "commandType": "estop",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_estop",
    "targetNodes": [
      "robot_control",
      "robot_decision"
    ],
    "timeoutBudgetMs": 1000,
    "fallbackPaths": [],
    "denyConditions": [
      "readonly_session",
      "observer_surface"
    ],
    "rollbackPaths": [
      "resume_from_safe_stop",
      "reset_fault"
    ],
    "allowedModes": [
      "IDLE",
      "MANUAL",
      "PATROL",
      "TRACK",
      "SAFE_STOP",
      "FAULT",
      "BOOT"
    ],
    "targetMode": "SAFE_STOP",
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": [
      "Emergency stop is intentionally permissive in mode coverage but still requires authoritative write access."
    ]
  },
  "pause_patrol": {
    "commandType": "pause_patrol",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_pause_patrol",
    "targetNodes": [
      "robot_decision",
      "robot_navigation"
    ],
    "timeoutBudgetMs": 3000,
    "fallbackPaths": [
      "cancel_action_then_set_mode_idle"
    ],
    "denyConditions": [
      "readonly_session",
      "observer_surface",
      "mode_guard_rejected"
    ],
    "rollbackPaths": [
      "stop_patrol",
      "set_mode:IDLE"
    ],
    "allowedModes": [
      "PATROL",
      "TRACK"
    ],
    "targetMode": "IDLE",
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": []
  },
  "reset_fault": {
    "commandType": "reset_fault",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_reset_fault",
    "targetNodes": [
      "robot_decision",
      "robot_control"
    ],
    "timeoutBudgetMs": 3000,
    "fallbackPaths": [],
    "denyConditions": [
      "readonly_session",
      "observer_surface",
      "fault_not_resettable"
    ],
    "rollbackPaths": [
      "estop"
    ],
    "allowedModes": [
      "FAULT",
      "SAFE_STOP"
    ],
    "targetMode": null,
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": []
  },
  "resume_from_safe_stop": {
    "commandType": "resume_from_safe_stop",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_resume_from_safe_stop",
    "targetNodes": [
      "robot_decision",
      "robot_control"
    ],
    "timeoutBudgetMs": 2500,
    "fallbackPaths": [],
    "denyConditions": [
      "readonly_session",
      "observer_surface",
      "safe_stop_not_recoverable"
    ],
    "rollbackPaths": [
      "estop",
      "set_mode:SAFE_STOP"
    ],
    "allowedModes": [
      "SAFE_STOP"
    ],
    "targetMode": "IDLE",
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": []
  },
  "save_snapshot": {
    "commandType": "save_snapshot",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_save_snapshot",
    "targetNodes": [
      "robot_vision"
    ],
    "timeoutBudgetMs": 8000,
    "fallbackPaths": [
      "action:/robot/actions/save_snapshot",
      "service:/robot/save_snapshot"
    ],
    "denyConditions": [
      "readonly_session",
      "observer_surface"
    ],
    "rollbackPaths": [
      "retry_snapshot_capture"
    ],
    "allowedModes": [
      "IDLE",
      "MANUAL",
      "PATROL",
      "TRACK",
      "SAFE_STOP",
      "FAULT"
    ],
    "targetMode": null,
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": [
      "Action route is preferred; service fallback remains for compatibility."
    ]
  },
  "set_mode": {
    "commandType": "set_mode",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_set_mode",
    "targetNodes": [
      "robot_decision",
      "robot_control"
    ],
    "timeoutBudgetMs": 3000,
    "fallbackPaths": [],
    "denyConditions": [
      "readonly_session",
      "observer_surface",
      "mode_transition_guard_rejected"
    ],
    "rollbackPaths": [
      "set_mode:IDLE",
      "estop"
    ],
    "allowedModes": [
      "IDLE",
      "MANUAL",
      "PATROL",
      "TRACK",
      "SAFE_STOP",
      "FAULT"
    ],
    "targetMode": null,
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": []
  },
  "speak_fixed_text": {
    "commandType": "speak_fixed_text",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_speak_fixed_text",
    "targetNodes": [
      "robot_voice"
    ],
    "timeoutBudgetMs": 4000,
    "fallbackPaths": [
      "topic:/robot/speak_req"
    ],
    "denyConditions": [
      "readonly_session",
      "observer_surface",
      "empty_speak_text",
      "invalid_speak_priority"
    ],
    "rollbackPaths": [
      "disable_voice_ingress_route"
    ],
    "allowedModes": [
      "BOOT",
      "IDLE",
      "MANUAL",
      "PATROL",
      "TRACK",
      "SAFE_STOP",
      "FAULT"
    ],
    "targetMode": null,
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": [
      "Topic route proves publication into robot_voice only; physical speaker output remains target acceptance evidence."
    ]
  },
  "start_patrol": {
    "commandType": "start_patrol",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_start_patrol",
    "targetNodes": [
      "robot_decision",
      "robot_navigation"
    ],
    "timeoutBudgetMs": 4000,
    "fallbackPaths": [],
    "denyConditions": [
      "readonly_session",
      "observer_surface",
      "navigation_lane_unavailable",
      "mode_transition_guard_rejected"
    ],
    "rollbackPaths": [
      "pause_patrol",
      "stop_patrol",
      "switch_provider_to_simple_nav_provider"
    ],
    "allowedModes": [
      "IDLE"
    ],
    "targetMode": "PATROL",
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": []
  },
  "stop_now": {
    "commandType": "stop_now",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_stop_now",
    "targetNodes": [
      "robot_control"
    ],
    "timeoutBudgetMs": 800,
    "fallbackPaths": [],
    "denyConditions": [
      "readonly_session",
      "observer_surface"
    ],
    "rollbackPaths": [
      "estop"
    ],
    "allowedModes": [
      "MANUAL",
      "PATROL",
      "TRACK",
      "SAFE_STOP",
      "FAULT",
      "IDLE"
    ],
    "targetMode": null,
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": []
  },
  "stop_patrol": {
    "commandType": "stop_patrol",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_stop_patrol",
    "targetNodes": [
      "robot_decision",
      "robot_navigation"
    ],
    "timeoutBudgetMs": 3000,
    "fallbackPaths": [
      "cancel_action_then_set_mode_idle"
    ],
    "denyConditions": [
      "readonly_session",
      "observer_surface",
      "mode_guard_rejected"
    ],
    "rollbackPaths": [
      "set_mode:IDLE",
      "switch_provider_to_simple_nav_provider"
    ],
    "allowedModes": [
      "PATROL",
      "TRACK",
      "MANUAL",
      "SAFE_STOP"
    ],
    "targetMode": "IDLE",
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": []
  },
  "teleop_cmd": {
    "commandType": "teleop_cmd",
    "entrySurfaces": [
      "frontend_api_facade"
    ],
    "sessionPolicy": "robot_contracts.command_policy:resolve_session_policy",
    "dispatchTransport": "robot_api_server -> internal_command_socket -> robot_web_bridge",
    "bridgeHandler": "handle_teleop",
    "targetNodes": [
      "robot_control",
      "robot_bridge"
    ],
    "timeoutBudgetMs": 250,
    "fallbackPaths": [
      "latest_only_supersession"
    ],
    "denyConditions": [
      "readonly_session",
      "observer_surface",
      "mode_not_manual"
    ],
    "rollbackPaths": [
      "stop_now",
      "estop",
      "disable_operator_session"
    ],
    "allowedModes": [
      "MANUAL"
    ],
    "targetMode": null,
    "terminalLifecycleStatuses": [
      "applied",
      "completed",
      "rejected",
      "denied",
      "timeout",
      "cancelled"
    ],
    "notes": [
      "latest-only queue replacement is authoritative for teleop_cmd."
    ]
  }
} as const;
        export const surfaceRegistry = {
  "bridge_observer_surface": {
    "surfaceId": "bridge_observer_surface",
    "surfaceLayers": [
      "live_state_projection",
      "observability_report"
    ],
    "authorityModel": "observer_only_runtime_projection",
    "defaultTransport": "ws://<host>:9001/ws",
    "writeEnabled": false,
    "machineGateAllowed": false,
    "truthSourcePaths": [
      "docs/architecture.md",
      "docs/protocols/bridge-contract.md",
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/web_bridge_node.py",
      "robot_frontend/src/bridge/policyKernel.ts"
    ],
    "notes": [
      "9001 bridge observer surface must hard-reject writes.",
      "Reports on this surface are human-facing observability unless separately promoted by governance."
    ]
  },
  "debug_observability_surface": {
    "surfaceId": "debug_observability_surface",
    "surfaceLayers": [
      "live_state_projection",
      "observability_report"
    ],
    "authorityModel": "localhost_only_readonly_proxy_runtime",
    "defaultTransport": "rosbridge-compatible readonly websocket",
    "writeEnabled": false,
    "machineGateAllowed": false,
    "truthSourcePaths": [
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/standard_observability_contract.py",
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/standard_observability_bridge_runtime.py",
      "docs/governance/repository-boundaries.md"
    ],
    "notes": [
      "Readonly debug bridge is localhost-scoped and intentionally does not expose operator command ingress."
    ]
  },
  "frontend_api_facade": {
    "surfaceId": "frontend_api_facade",
    "surfaceLayers": [
      "command_control",
      "live_state_projection",
      "observability_report"
    ],
    "authorityModel": "authoritative_write_via_api_server_session_policy",
    "defaultTransport": "ws://<host>:9100/ws and /api/v1/*",
    "writeEnabled": true,
    "machineGateAllowed": false,
    "truthSourcePaths": [
      "docs/architecture.md",
      "docs/protocols/bridge-contract.md",
      "ros2_ws/src/robot_api_server/robot_api_server/proxy_server.py",
      "robot_frontend/src/bridge/policyKernel.ts"
    ],
    "notes": [
      "9100 API facade is the only operator-authoritative write surface.",
      "This surface may mirror live state and reports but write semantics remain authoritative-only."
    ]
  },
  "release_reports": {
    "surfaceId": "release_reports",
    "surfaceLayers": [
      "replay_export"
    ],
    "authorityModel": "offline_release_evidence_bundle",
    "defaultTransport": "json/mcap/zip artifacts",
    "writeEnabled": false,
    "machineGateAllowed": true,
    "truthSourcePaths": [
      "docs/governance/replay-evidence.md",
      "scripts/build_system_replay_bundle.py",
      "scripts/render_system_replay_report.py"
    ],
    "notes": [
      "Release evidence is offline and must not be conflated with online command channels."
    ]
  }
} as const;
        export const runtimeOrchestrationRegistry = {
  "bond_supervision": {
    "componentId": "bond_supervision",
    "reportKey": "runtimeSupervision",
    "requiredForMainline": false,
    "runtimeTopics": [
      "/robot/runtime/supervision"
    ],
    "operatorVisibleFields": [
      "bondSupervision.present",
      "bondSupervision.type",
      "bondSupervision.state",
      "bondSupervision.managedNodes"
    ],
    "truthSourcePaths": [
      "ros2_ws/src/robot_bringup/robot_bringup/ros_lifecycle_manager.py",
      "ros2_ws/src/robot_bringup/robot_bringup/runtime_orchestration_manager.py",
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py"
    ],
    "recoveryOwner": "ros_lifecycle_manager",
    "notes": [
      "Bond supervision complements lifecycle state and is used to explain degraded recovery conditions."
    ]
  },
  "lifecycle_manager": {
    "componentId": "lifecycle_manager",
    "reportKey": "runtimeSupervision",
    "requiredForMainline": false,
    "runtimeTopics": [
      "/robot/runtime/supervision"
    ],
    "operatorVisibleFields": [
      "lifecycleManager.present",
      "lifecycleManager.type",
      "lifecycleManager.state",
      "lifecycleManager.managedNodes",
      "lifecycleManager.recentTransitions"
    ],
    "truthSourcePaths": [
      "ros2_ws/src/robot_bringup/robot_bringup/ros_lifecycle_manager.py",
      "ros2_ws/src/robot_bringup/robot_bringup/runtime_orchestration_manager.py",
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py"
    ],
    "recoveryOwner": "ros_lifecycle_manager",
    "notes": [
      "Lifecycle manager state is observability-first and must not be assumed present on every profile."
    ]
  },
  "operator_surface_readiness": {
    "componentId": "operator_surface_readiness",
    "reportKey": "runtimeSupervision",
    "requiredForMainline": true,
    "runtimeTopics": [
      "/robot/web_bridge/ready",
      "/robot/runtime/supervision"
    ],
    "operatorVisibleFields": [
      "startupBarrierReady",
      "readiness",
      "reasons"
    ],
    "truthSourcePaths": [
      "robot_frontend/src/bridge/policyKernel.ts",
      "ros2_ws/src/robot_bringup/robot_bringup/runtime_orchestration_manager.py",
      "ros2_ws/src/robot_api_server/robot_api_server/proxy_server.py",
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/web_bridge_node.py"
    ],
    "recoveryOwner": "robot_api_server",
    "notes": [
      "Operator-ready status spans API facade readiness, web-bridge readiness, and runtime supervision."
    ]
  },
  "recovery_plan": {
    "componentId": "recovery_plan",
    "reportKey": "runtimeSupervision",
    "requiredForMainline": true,
    "runtimeTopics": [
      "/robot/runtime/supervision"
    ],
    "operatorVisibleFields": [
      "recoveryMode",
      "recoveryPlan.strategy",
      "recoveryPlan.reason",
      "recoveryPlan.targetNodes"
    ],
    "truthSourcePaths": [
      "ros2_ws/src/robot_bringup/robot_bringup/runtime_orchestration_manager.py",
      "ros2_ws/src/robot_decision/robot_decision/decision_app_service.py",
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py"
    ],
    "recoveryOwner": "robot_decision",
    "notes": [
      "Recovery-plan reporting must stay aligned with runtime supervision and operator-facing safe-stop guidance."
    ]
  },
  "startup_barrier": {
    "componentId": "startup_barrier",
    "reportKey": "runtimeSupervision",
    "requiredForMainline": true,
    "runtimeTopics": [
      "/robot/runtime/supervision",
      "/robot/web_bridge/ready"
    ],
    "operatorVisibleFields": [
      "startupBarrierReady",
      "readiness",
      "reasons"
    ],
    "truthSourcePaths": [
      "ros2_ws/src/robot_bringup/robot_bringup/startup_barrier.py",
      "ros2_ws/src/robot_bringup/robot_bringup/runtime_orchestration_manager.py",
      "ros2_ws/src/robot_web_bridge/robot_web_bridge/components/observability_surface.py"
    ],
    "recoveryOwner": "startup_barrier",
    "notes": [
      "Startup barrier readiness is the first operator-visible gate before command entry is considered ready."
    ]
  }
} as const;
        export const navigationAdapterBoundaryRegistry = {
  "nav2_provider": {
    "laneId": "navigation.nav2_provider",
    "providerName": "nav2_provider",
    "boundaryRole": "governed_adapter_boundary",
    "packageName": "robot_nav2_adapter",
    "executable": "nav2_adapter_node",
    "adapterRuntime": true,
    "defaultMainline": false,
    "promotionChecklist": [
      "simulation_smoke",
      "host_harness_smoke",
      "provider_switch_smoke",
      "operator_docs_review",
      "target_environment_acceptance",
      "external_backend_smoke"
    ],
    "rollbackBaseline": "simple_nav_provider",
    "nonClaims": [
      "does_not_claim_external_nav2_backend_integration_when_running_local_adapter",
      "does_not_claim_nav2_planner_controller_recovery_servers_present_without_backend_integration"
    ],
    "truthSourcePaths": [
      "ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py",
      "ros2_ws/src/robot_nav2_adapter/robot_nav2_adapter/backend_claims.py",
      "ros2_ws/src/robot_nav2_adapter/robot_nav2_adapter/nav2_adapter_node.py"
    ]
  },
  "simple_nav_provider": {
    "laneId": "navigation.simple_nav_provider",
    "providerName": "simple_nav_provider",
    "boundaryRole": "mainline_provider",
    "packageName": "robot_navigation",
    "executable": "navigation_node",
    "adapterRuntime": false,
    "defaultMainline": true,
    "promotionChecklist": [
      "host_harness_smoke"
    ],
    "rollbackBaseline": "self",
    "nonClaims": [
      "does_not_claim_external_nav2_stack"
    ],
    "truthSourcePaths": [
      "ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py",
      "ros2_ws/src/robot_navigation/robot_navigation/navigation_node.py"
    ]
  }
} as const;
        export const releaseGateRegistry = {
  "command_route_governance": {
    "gateId": "command_route_governance",
    "title": "命令路由权威矩阵",
    "entrypoint": "python3 scripts/check_command_route_registry.py",
    "scriptPaths": [
      "scripts/check_command_route_registry.py"
    ],
    "workflowMarkers": [
      "Command route registry",
      "python3 scripts/check_command_route_registry.py"
    ],
    "readmeMarkers": [
      "check_command_route_registry.py"
    ],
    "stage": "governance",
    "riskSurface": "command_path_truth",
    "blockingByDefault": true,
    "notes": [
      "命令入口、权限、目标节点、超时与回滚路径必须完整覆盖全部命令。"
    ]
  },
  "contract_consistency": {
    "gateId": "contract_consistency",
    "title": "跨表面合同一致性",
    "entrypoint": "python3 scripts/check_contract_consistency.py",
    "scriptPaths": [
      "scripts/check_contract_consistency.py",
      "scripts/check_report_surface_closure.py",
      "scripts/check_report_kind_enum_closure.py"
    ],
    "workflowMarkers": [
      "Contract consistency",
      "Report surface closure",
      "Report kind enum closure"
    ],
    "readmeMarkers": [
      "check_contract_consistency.py",
      "check_report_surface_closure.py",
      "check_report_kind_enum_closure.py"
    ],
    "stage": "governance",
    "riskSurface": "contract_drift",
    "blockingByDefault": true,
    "notes": [
      "协议版本、生成工件、报告面枚举闭包必须来自同一真源。"
    ]
  },
  "feature_admission": {
    "gateId": "feature_admission",
    "title": "功能准入与 UI 绑定",
    "entrypoint": "python3 scripts/check_feature_admission.py",
    "scriptPaths": [
      "scripts/check_feature_admission.py"
    ],
    "workflowMarkers": [
      "Feature admission registry",
      "python3 scripts/check_feature_admission.py"
    ],
    "readmeMarkers": [
      "check_feature_admission.py"
    ],
    "stage": "governance",
    "riskSurface": "feature_ui_alignment",
    "blockingByDefault": true,
    "notes": [
      "命令、能力、UI 消费者和验收证据必须同源。"
    ]
  },
  "frontend_e2e": {
    "gateId": "frontend_e2e",
    "title": "Frontend E2E",
    "entrypoint": "./scripts/run_release_verification.sh --with-frontend",
    "scriptPaths": [
      "scripts/run_release_verification.sh",
      "scripts/run_frontend_workspace_command.py"
    ],
    "workflowMarkers": [
      "Install Playwright browsers (isolated workspace)",
      "python3 scripts/run_frontend_workspace_command.py -- npm exec playwright install --with-deps chromium",
      "Frontend E2E",
      "python3 scripts/run_frontend_workspace_command.py -- npm run test:e2e:ci"
    ],
    "readmeMarkers": [
      "run_release_verification.sh --with-frontend",
      "Frontend E2E"
    ],
    "stage": "verification",
    "riskSurface": "frontend_health",
    "blockingByDefault": true,
    "notes": [
      "前端 E2E 是操作面最小健康门。"
    ]
  },
  "integrated_frontend_bridge_smoke": {
    "gateId": "integrated_frontend_bridge_smoke",
    "title": "Integrated frontend + web bridge smoke",
    "entrypoint": "./scripts/run_release_verification.sh --with-integrated-frontend-smoke --skip-npm-ci",
    "scriptPaths": [
      "scripts/run_release_verification.sh"
    ],
    "workflowMarkers": [
      "integrated_frontend_bridge_smoke:",
      "Integrated frontend + web bridge smoke",
      "./scripts/run_release_verification.sh --with-integrated-frontend-smoke --skip-npm-ci"
    ],
    "readmeMarkers": [
      "Integrated frontend + web bridge smoke"
    ],
    "stage": "verification",
    "riskSurface": "end_to_end_operator_path",
    "blockingByDefault": true,
    "notes": [
      "前端与 bridge 集成烟测覆盖 9100/9001 入口的最小操作路径。"
    ]
  },
  "lane_alignment": {
    "gateId": "lane_alignment",
    "title": "实验 lane 与 adapter 边界一致性",
    "entrypoint": "python3 scripts/check_lane_implementation_alignment.py",
    "scriptPaths": [
      "scripts/check_lane_implementation_alignment.py"
    ],
    "workflowMarkers": [
      "Lane implementation alignment",
      "python3 scripts/check_lane_implementation_alignment.py"
    ],
    "readmeMarkers": [
      "check_lane_implementation_alignment.py"
    ],
    "stage": "governance",
    "riskSurface": "adapter_boundary_truth",
    "blockingByDefault": true,
    "notes": [
      "实验 Nav2 lane 只能按受控适配器边界宣称能力。"
    ]
  },
  "ros_smoke": {
    "gateId": "ros_smoke",
    "title": "Mock system web bridge launch smoke",
    "entrypoint": "./scripts/run_release_verification.sh --with-ros-smoke",
    "scriptPaths": [
      "scripts/run_release_verification.sh"
    ],
    "workflowMarkers": [
      "Mock system web bridge launch smoke",
      "--launch-file mock_system.launch.py",
      "--expected-node /robot_web_bridge"
    ],
    "readmeMarkers": [
      "Mock system web bridge launch smoke"
    ],
    "stage": "verification",
    "riskSurface": "bridge_integration",
    "blockingByDefault": true,
    "notes": [
      "ROS mock smoke 用于确认 web bridge 入口仍可起。"
    ]
  },
  "source_release_cleanliness": {
    "gateId": "source_release_cleanliness",
    "title": "干净源码树与打包审计",
    "entrypoint": "python3 scripts/package_source_release.py --clean-transient-source-artifacts",
    "scriptPaths": [
      "scripts/package_source_release.py",
      "scripts/refresh_validation_evidence_metadata.py"
    ],
    "workflowMarkers": [
      "Source release package audit",
      "python3 scripts/package_source_release.py --clean-transient-source-artifacts",
      "Clean source tree gate (pre-frontend)",
      "Clean source tree gate (post-frontend)"
    ],
    "readmeMarkers": [
      "canonical-only source release",
      "check_validation_evidence_binding.py"
    ],
    "stage": "package",
    "riskSurface": "source_package_cleanliness",
    "blockingByDefault": true,
    "notes": [
      "打包前后均应阻止 build/dist/node_modules 等污染进入交付包。",
      "打包过程必须刷新 validation evidence 元数据，避免旧源码树哈希复用。"
    ]
  },
  "target_environment_acceptance": {
    "gateId": "target_environment_acceptance",
    "title": "Target environment acceptance capture",
    "entrypoint": "./scripts/run_target_environment_acceptance.sh --allow-incomplete --output /tmp/target_environment_acceptance.json",
    "scriptPaths": [
      "scripts/run_target_environment_acceptance.sh"
    ],
    "workflowMarkers": [
      "Target environment acceptance capture",
      "./scripts/run_target_environment_acceptance.sh --allow-incomplete --output /tmp/target_environment_acceptance.json"
    ],
    "readmeMarkers": [
      "--config-path"
    ],
    "stage": "verification",
    "riskSurface": "target_environment_evidence",
    "blockingByDefault": false,
    "notes": [
      "目标环境验收采集存在环境依赖，默认不作为 PR 阻断。"
    ]
  },
  "validation_evidence_binding": {
    "gateId": "validation_evidence_binding",
    "title": "验证证据绑定",
    "entrypoint": "python3 scripts/check_validation_evidence_binding.py",
    "scriptPaths": [
      "scripts/check_validation_evidence_binding.py",
      "scripts/refresh_validation_evidence_metadata.py"
    ],
    "workflowMarkers": [
      "Validation evidence binding",
      "python3 scripts/check_validation_evidence_binding.py"
    ],
    "readmeMarkers": [
      "check_validation_evidence_binding.py",
      "VALIDATION_EVIDENCE.md"
    ],
    "stage": "governance",
    "riskSurface": "validation_truthfulness",
    "blockingByDefault": true,
    "notes": [
      "交付包中的 validation evidence 必须绑定当前源码树与 workspace manifest。"
    ]
  }
} as const;
        export const profileRegistry = {
  "demo": {
    "profileName": "demo",
    "profile": {
      "name": "demo",
      "enable_voice": true,
      "enable_vision": true,
      "enable_monitor": true,
      "enable_teleop": false,
      "enable_localization": true,
      "enable_navigation": true,
      "enable_hardware_interface": true,
      "enable_api_server": true,
      "log_level": "info",
      "use_mock_robot": false,
      "enable_debug_overlay": false,
      "diagnostics_enabled": true,
      "enable_web_bridge": true,
      "preflight_checks_enabled": true,
      "bridge_host": "192.168.4.1",
      "bridge_port": 9000,
      "mjpeg_url": "http://192.168.4.1:81/stream",
      "websocket_public_host": "192.168.4.1",
      "websocket_listen_host": "127.0.0.1",
      "websocket_port": 9001,
      "websocket_path": "/ws",
      "api_server_public_host": "127.0.0.1",
      "api_server_listen_host": "127.0.0.1",
      "api_server_port": 9100,
      "api_server_ws_path": "/ws",
      "api_server_api_prefix": "/api/v1",
      "description": "演示配置，连接真实 ESP32-S3 网关。",
      "tags": [
        "demo",
        "hardware"
      ],
      "enabled_nodes": [
        "robot_decision",
        "robot_control",
        "robot_bridge",
        "robot_voice",
        "robot_vision",
        "robot_monitor",
        "robot_web_bridge",
        "robot_localization",
        "robot_navigation",
        "robot_hardware_interface",
        "robot_api_server"
      ],
      "feature_matrix": {
        "voice": true,
        "vision": true,
        "monitor": true,
        "teleop": false,
        "mock_robot": false,
        "debug_overlay": false,
        "diagnostics": true,
        "web_bridge": true,
        "localization": true,
        "navigation": true,
        "hardware_interface": true,
        "api_server": true,
        "preflight_checks": true
      },
      "runtime": {
        "mock_enabled": false,
        "bridge": {
          "host": "192.168.4.1",
          "port": 9000,
          "mjpeg_url": "http://192.168.4.1:81/stream"
        },
        "web_bridge_enabled": true
      },
      "operational_class": "hardware_stable",
      "deployment_tier": "real_robot",
      "hardware_boundary_mode": "ubuntu_runtime_plus_board_boundary_contract",
      "startup_sequence": [
        "contracts",
        "bridge",
        "control",
        "monitor",
        "platform",
        "vision_voice",
        "navigation",
        "lifecycle",
        "decision",
        "frontend"
      ],
      "runtime_supervision": {
        "startupBarrierEnabled": true,
        "startupBarrierPhases": [
          "contracts",
          "bridge",
          "control",
          "monitor",
          "platform",
          "vision_voice",
          "navigation",
          "lifecycle",
          "decision",
          "frontend"
        ],
        "runtimeHealthSurface": "connection.runtimeHealthState/runtimeHealthReasons",
        "startupReadinessSurface": "/robot/web_bridge/ready",
        "supervisionMode": "startup_barrier_plus_ros_lifecycle_manager",
        "operatorSurfaceContract": {
          "enabled": true,
          "required_nodes": [
            "robot_web_bridge"
          ],
          "ready_topics": [
            "/robot/web_bridge/ready"
          ],
          "ready_http_urls": [
            "http://127.0.0.1:9100/api/v1/health"
          ],
          "require_operator_ready": true
        },
        "surfaceMatrix": {
          "backend": {
            "enabled": true,
            "required_nodes": [
              "robot_decision",
              "robot_control",
              "robot_bridge"
            ],
            "ready_topics": [],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "web_bridge": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "frontend": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [
              "http://127.0.0.1:9100/api/v1/health"
            ],
            "require_operator_ready": true
          }
        },
        "failureTaxonomy": {
          "startup": {
            "missing_node": {
              "severity": "fatal",
              "operator_action": "inspect_launch_and_process_logs"
            },
            "missing_ready_topic": {
              "severity": "fatal",
              "operator_action": "wait_for_startup_barrier_or_restart_surface"
            },
            "missing_http_probe": {
              "severity": "fatal",
              "operator_action": "inspect_api_server_or_surface_health_endpoint"
            },
            "preflight_failed": {
              "severity": "fatal",
              "operator_action": "resolve_reported_dependency_or_config_gap"
            }
          },
          "runtime": {
            "bridge_runtime_degraded": {
              "severity": "warn",
              "operator_action": "inspect_runtime_health_reasons_and_transport_stats"
            },
            "operator_surface_unready": {
              "severity": "warn",
              "operator_action": "check_websocket_gateway_and_frontend_connectivity"
            },
            "api_surface_unready": {
              "severity": "warn",
              "operator_action": "inspect_api_server_runtime_health_and_operator_ready_reasons"
            },
            "runtime_param_timeout": {
              "severity": "warn",
              "operator_action": "inspect_consumer_status_and_retry_or_rollback"
            }
          }
        },
        "runtimeSupervisorPresent": true,
        "lifecycleManagerPresent": true,
        "lifecycleManagerType": "ros_lifecycle_manager",
        "bondSupervisionPresent": true,
        "bondSupervisionType": "bondpy_supervision",
        "recoveryMode": "ros_lifecycle_manager_safe_shutdown_and_manual_reactivate",
        "runtimeSupervisionTopic": "/robot/runtime/supervision",
        "runtimeOrchestrationTopic": "/robot/runtime/orchestration",
        "runtimeOrchestrationReadyTopic": "/robot/runtime/orchestration/ready",
        "runtimeLifecycleSurface": "/robot/lifecycle_manager/status.lifecycleManager",
        "runtimeBondSurface": "/robot/lifecycle_manager/status.bondSupervision",
        "runtimeRecoveryPlanSurface": "/robot/lifecycle_manager/status.recoveryPlan",
        "lifecycleManagerStatusTopic": "/robot/lifecycle_manager/status",
        "lifecycleManagerReadyTopic": "/robot/lifecycle_manager/ready",
        "notes": [
          "startup barrier readiness and runtime supervision are modeled separately so startup success is not mistaken for runtime stability",
          "operator surface readiness requires the web bridge ready topic and the API health contract when API server is enabled",
          "the bringup stack now launches ROS lifecycle wrapper nodes and a ROS lifecycle manager that configures and activates managed components through lifecycle_msgs services",
          "bond supervision is provided by bondpy on the ROS bond topic and lifecycle degradation is surfaced through /robot/lifecycle_manager/status",
          "localization/hardware-interface/api-server remain optional per profile and are reported through the supervision component map when the monitor is enabled",
          "runtime supervisor publishes /robot/runtime/supervision and embeds authoritative lifecycleManager / bondSupervision / recoveryPlan sections from the ROS lifecycle manager status topic",
          "runtime orchestration manager publishes /robot/runtime/orchestration and /robot/runtime/orchestration/ready so startup, pause, recovery, degraded, and shutdown phases share one bringup-level state machine"
        ]
      }
    },
    "startupSequence": [
      "contracts",
      "bridge",
      "control",
      "monitor",
      "platform",
      "vision_voice",
      "navigation",
      "lifecycle",
      "decision",
      "frontend"
    ],
    "capabilityMatrix": {
      "voice": true,
      "vision": true,
      "monitor": true,
      "teleop": false,
      "localization": true,
      "navigation": true,
      "hardware_interface": true,
      "api_server": true,
      "web_bridge": true,
      "mock_robot": false,
      "debug_overlay": false,
      "diagnostics": true,
      "preflight_checks": true
    },
    "surfaceContract": {
      "backend": {
        "enabled": true,
        "required_nodes": [
          "robot_decision",
          "robot_control",
          "robot_bridge"
        ],
        "ready_topics": [],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "web_bridge": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "frontend": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [
          "http://127.0.0.1:9100/api/v1/health"
        ],
        "require_operator_ready": true
      }
    }
  },
  "dev": {
    "profileName": "dev",
    "profile": {
      "name": "dev",
      "enable_voice": true,
      "enable_vision": true,
      "enable_monitor": true,
      "enable_teleop": true,
      "enable_localization": true,
      "enable_navigation": true,
      "enable_hardware_interface": true,
      "enable_api_server": true,
      "log_level": "debug",
      "use_mock_robot": true,
      "enable_debug_overlay": true,
      "diagnostics_enabled": true,
      "enable_web_bridge": true,
      "preflight_checks_enabled": true,
      "bridge_host": "127.0.0.1",
      "bridge_port": 9000,
      "mjpeg_url": "http://127.0.0.1:8080/stream",
      "websocket_public_host": "127.0.0.1",
      "websocket_listen_host": "127.0.0.1",
      "websocket_port": 9001,
      "websocket_path": "/ws",
      "api_server_public_host": "127.0.0.1",
      "api_server_listen_host": "127.0.0.1",
      "api_server_port": 9100,
      "api_server_ws_path": "/ws",
      "api_server_api_prefix": "/api/v1",
      "description": "开发联调配置，默认挂接本地 mock 机器人和 Web 控制台。",
      "tags": [
        "dev",
        "mock"
      ],
      "enabled_nodes": [
        "robot_decision",
        "robot_control",
        "robot_bridge",
        "robot_voice",
        "robot_vision",
        "robot_monitor",
        "robot_teleop",
        "robot_web_bridge",
        "robot_localization",
        "robot_navigation",
        "robot_hardware_interface",
        "robot_api_server"
      ],
      "feature_matrix": {
        "voice": true,
        "vision": true,
        "monitor": true,
        "teleop": true,
        "mock_robot": true,
        "debug_overlay": true,
        "diagnostics": true,
        "web_bridge": true,
        "localization": true,
        "navigation": true,
        "hardware_interface": true,
        "api_server": true,
        "preflight_checks": true
      },
      "runtime": {
        "mock_enabled": true,
        "bridge": {
          "host": "127.0.0.1",
          "port": 9000,
          "mjpeg_url": "http://127.0.0.1:8080/stream"
        },
        "web_bridge_enabled": true
      },
      "operational_class": "mock",
      "deployment_tier": "host_harness",
      "hardware_boundary_mode": "host_harness_only",
      "startup_sequence": [
        "contracts",
        "bridge",
        "control",
        "monitor",
        "platform",
        "vision_voice",
        "navigation",
        "lifecycle",
        "decision",
        "frontend"
      ],
      "runtime_supervision": {
        "startupBarrierEnabled": true,
        "startupBarrierPhases": [
          "contracts",
          "bridge",
          "control",
          "monitor",
          "platform",
          "vision_voice",
          "navigation",
          "lifecycle",
          "decision",
          "frontend"
        ],
        "runtimeHealthSurface": "connection.runtimeHealthState/runtimeHealthReasons",
        "startupReadinessSurface": "/robot/web_bridge/ready",
        "supervisionMode": "startup_barrier_plus_ros_lifecycle_manager",
        "operatorSurfaceContract": {
          "enabled": true,
          "required_nodes": [
            "robot_web_bridge"
          ],
          "ready_topics": [
            "/robot/web_bridge/ready"
          ],
          "ready_http_urls": [
            "http://127.0.0.1:9100/api/v1/health"
          ],
          "require_operator_ready": true
        },
        "surfaceMatrix": {
          "backend": {
            "enabled": true,
            "required_nodes": [
              "robot_decision",
              "robot_control",
              "robot_bridge"
            ],
            "ready_topics": [],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "web_bridge": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "frontend": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [
              "http://127.0.0.1:9100/api/v1/health"
            ],
            "require_operator_ready": true
          }
        },
        "failureTaxonomy": {
          "startup": {
            "missing_node": {
              "severity": "fatal",
              "operator_action": "inspect_launch_and_process_logs"
            },
            "missing_ready_topic": {
              "severity": "fatal",
              "operator_action": "wait_for_startup_barrier_or_restart_surface"
            },
            "missing_http_probe": {
              "severity": "fatal",
              "operator_action": "inspect_api_server_or_surface_health_endpoint"
            },
            "preflight_failed": {
              "severity": "fatal",
              "operator_action": "resolve_reported_dependency_or_config_gap"
            }
          },
          "runtime": {
            "bridge_runtime_degraded": {
              "severity": "warn",
              "operator_action": "inspect_runtime_health_reasons_and_transport_stats"
            },
            "operator_surface_unready": {
              "severity": "warn",
              "operator_action": "check_websocket_gateway_and_frontend_connectivity"
            },
            "api_surface_unready": {
              "severity": "warn",
              "operator_action": "inspect_api_server_runtime_health_and_operator_ready_reasons"
            },
            "runtime_param_timeout": {
              "severity": "warn",
              "operator_action": "inspect_consumer_status_and_retry_or_rollback"
            }
          }
        },
        "runtimeSupervisorPresent": true,
        "lifecycleManagerPresent": true,
        "lifecycleManagerType": "ros_lifecycle_manager",
        "bondSupervisionPresent": true,
        "bondSupervisionType": "bondpy_supervision",
        "recoveryMode": "ros_lifecycle_manager_safe_shutdown_and_manual_reactivate",
        "runtimeSupervisionTopic": "/robot/runtime/supervision",
        "runtimeOrchestrationTopic": "/robot/runtime/orchestration",
        "runtimeOrchestrationReadyTopic": "/robot/runtime/orchestration/ready",
        "runtimeLifecycleSurface": "/robot/lifecycle_manager/status.lifecycleManager",
        "runtimeBondSurface": "/robot/lifecycle_manager/status.bondSupervision",
        "runtimeRecoveryPlanSurface": "/robot/lifecycle_manager/status.recoveryPlan",
        "lifecycleManagerStatusTopic": "/robot/lifecycle_manager/status",
        "lifecycleManagerReadyTopic": "/robot/lifecycle_manager/ready",
        "notes": [
          "startup barrier readiness and runtime supervision are modeled separately so startup success is not mistaken for runtime stability",
          "operator surface readiness requires the web bridge ready topic and the API health contract when API server is enabled",
          "the bringup stack now launches ROS lifecycle wrapper nodes and a ROS lifecycle manager that configures and activates managed components through lifecycle_msgs services",
          "bond supervision is provided by bondpy on the ROS bond topic and lifecycle degradation is surfaced through /robot/lifecycle_manager/status",
          "localization/hardware-interface/api-server remain optional per profile and are reported through the supervision component map when the monitor is enabled",
          "runtime supervisor publishes /robot/runtime/supervision and embeds authoritative lifecycleManager / bondSupervision / recoveryPlan sections from the ROS lifecycle manager status topic",
          "runtime orchestration manager publishes /robot/runtime/orchestration and /robot/runtime/orchestration/ready so startup, pause, recovery, degraded, and shutdown phases share one bringup-level state machine"
        ]
      }
    },
    "startupSequence": [
      "contracts",
      "bridge",
      "control",
      "monitor",
      "platform",
      "vision_voice",
      "navigation",
      "lifecycle",
      "decision",
      "frontend"
    ],
    "capabilityMatrix": {
      "voice": true,
      "vision": true,
      "monitor": true,
      "teleop": true,
      "localization": true,
      "navigation": true,
      "hardware_interface": true,
      "api_server": true,
      "web_bridge": true,
      "mock_robot": true,
      "debug_overlay": true,
      "diagnostics": true,
      "preflight_checks": true
    },
    "surfaceContract": {
      "backend": {
        "enabled": true,
        "required_nodes": [
          "robot_decision",
          "robot_control",
          "robot_bridge"
        ],
        "ready_topics": [],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "web_bridge": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "frontend": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [
          "http://127.0.0.1:9100/api/v1/health"
        ],
        "require_operator_ready": true
      }
    }
  },
  "full": {
    "profileName": "full",
    "profile": {
      "name": "full",
      "enable_voice": true,
      "enable_vision": true,
      "enable_monitor": true,
      "enable_teleop": true,
      "enable_localization": true,
      "enable_navigation": true,
      "enable_hardware_interface": true,
      "enable_api_server": true,
      "log_level": "info",
      "use_mock_robot": false,
      "enable_debug_overlay": true,
      "diagnostics_enabled": true,
      "enable_web_bridge": true,
      "preflight_checks_enabled": true,
      "bridge_host": "192.168.4.1",
      "bridge_port": 9000,
      "mjpeg_url": "http://192.168.4.1:81/stream",
      "websocket_public_host": "192.168.4.1",
      "websocket_listen_host": "127.0.0.1",
      "websocket_port": 9001,
      "websocket_path": "/ws",
      "api_server_public_host": "127.0.0.1",
      "api_server_listen_host": "127.0.0.1",
      "api_server_port": 9100,
      "api_server_ws_path": "/ws",
      "api_server_api_prefix": "/api/v1",
      "description": "全功能运行配置。",
      "tags": [
        "ops",
        "hardware"
      ],
      "enabled_nodes": [
        "robot_decision",
        "robot_control",
        "robot_bridge",
        "robot_voice",
        "robot_vision",
        "robot_monitor",
        "robot_teleop",
        "robot_web_bridge",
        "robot_localization",
        "robot_navigation",
        "robot_hardware_interface",
        "robot_api_server"
      ],
      "feature_matrix": {
        "voice": true,
        "vision": true,
        "monitor": true,
        "teleop": true,
        "mock_robot": false,
        "debug_overlay": true,
        "diagnostics": true,
        "web_bridge": true,
        "localization": true,
        "navigation": true,
        "hardware_interface": true,
        "api_server": true,
        "preflight_checks": true
      },
      "runtime": {
        "mock_enabled": false,
        "bridge": {
          "host": "192.168.4.1",
          "port": 9000,
          "mjpeg_url": "http://192.168.4.1:81/stream"
        },
        "web_bridge_enabled": true
      },
      "operational_class": "hardware_debug",
      "deployment_tier": "real_robot",
      "hardware_boundary_mode": "ubuntu_runtime_plus_board_boundary_contract",
      "startup_sequence": [
        "contracts",
        "bridge",
        "control",
        "monitor",
        "platform",
        "vision_voice",
        "navigation",
        "lifecycle",
        "decision",
        "frontend"
      ],
      "runtime_supervision": {
        "startupBarrierEnabled": true,
        "startupBarrierPhases": [
          "contracts",
          "bridge",
          "control",
          "monitor",
          "platform",
          "vision_voice",
          "navigation",
          "lifecycle",
          "decision",
          "frontend"
        ],
        "runtimeHealthSurface": "connection.runtimeHealthState/runtimeHealthReasons",
        "startupReadinessSurface": "/robot/web_bridge/ready",
        "supervisionMode": "startup_barrier_plus_ros_lifecycle_manager",
        "operatorSurfaceContract": {
          "enabled": true,
          "required_nodes": [
            "robot_web_bridge"
          ],
          "ready_topics": [
            "/robot/web_bridge/ready"
          ],
          "ready_http_urls": [
            "http://127.0.0.1:9100/api/v1/health"
          ],
          "require_operator_ready": true
        },
        "surfaceMatrix": {
          "backend": {
            "enabled": true,
            "required_nodes": [
              "robot_decision",
              "robot_control",
              "robot_bridge"
            ],
            "ready_topics": [],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "web_bridge": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "frontend": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [
              "http://127.0.0.1:9100/api/v1/health"
            ],
            "require_operator_ready": true
          }
        },
        "failureTaxonomy": {
          "startup": {
            "missing_node": {
              "severity": "fatal",
              "operator_action": "inspect_launch_and_process_logs"
            },
            "missing_ready_topic": {
              "severity": "fatal",
              "operator_action": "wait_for_startup_barrier_or_restart_surface"
            },
            "missing_http_probe": {
              "severity": "fatal",
              "operator_action": "inspect_api_server_or_surface_health_endpoint"
            },
            "preflight_failed": {
              "severity": "fatal",
              "operator_action": "resolve_reported_dependency_or_config_gap"
            }
          },
          "runtime": {
            "bridge_runtime_degraded": {
              "severity": "warn",
              "operator_action": "inspect_runtime_health_reasons_and_transport_stats"
            },
            "operator_surface_unready": {
              "severity": "warn",
              "operator_action": "check_websocket_gateway_and_frontend_connectivity"
            },
            "api_surface_unready": {
              "severity": "warn",
              "operator_action": "inspect_api_server_runtime_health_and_operator_ready_reasons"
            },
            "runtime_param_timeout": {
              "severity": "warn",
              "operator_action": "inspect_consumer_status_and_retry_or_rollback"
            }
          }
        },
        "runtimeSupervisorPresent": true,
        "lifecycleManagerPresent": true,
        "lifecycleManagerType": "ros_lifecycle_manager",
        "bondSupervisionPresent": true,
        "bondSupervisionType": "bondpy_supervision",
        "recoveryMode": "ros_lifecycle_manager_safe_shutdown_and_manual_reactivate",
        "runtimeSupervisionTopic": "/robot/runtime/supervision",
        "runtimeOrchestrationTopic": "/robot/runtime/orchestration",
        "runtimeOrchestrationReadyTopic": "/robot/runtime/orchestration/ready",
        "runtimeLifecycleSurface": "/robot/lifecycle_manager/status.lifecycleManager",
        "runtimeBondSurface": "/robot/lifecycle_manager/status.bondSupervision",
        "runtimeRecoveryPlanSurface": "/robot/lifecycle_manager/status.recoveryPlan",
        "lifecycleManagerStatusTopic": "/robot/lifecycle_manager/status",
        "lifecycleManagerReadyTopic": "/robot/lifecycle_manager/ready",
        "notes": [
          "startup barrier readiness and runtime supervision are modeled separately so startup success is not mistaken for runtime stability",
          "operator surface readiness requires the web bridge ready topic and the API health contract when API server is enabled",
          "the bringup stack now launches ROS lifecycle wrapper nodes and a ROS lifecycle manager that configures and activates managed components through lifecycle_msgs services",
          "bond supervision is provided by bondpy on the ROS bond topic and lifecycle degradation is surfaced through /robot/lifecycle_manager/status",
          "localization/hardware-interface/api-server remain optional per profile and are reported through the supervision component map when the monitor is enabled",
          "runtime supervisor publishes /robot/runtime/supervision and embeds authoritative lifecycleManager / bondSupervision / recoveryPlan sections from the ROS lifecycle manager status topic",
          "runtime orchestration manager publishes /robot/runtime/orchestration and /robot/runtime/orchestration/ready so startup, pause, recovery, degraded, and shutdown phases share one bringup-level state machine"
        ]
      }
    },
    "startupSequence": [
      "contracts",
      "bridge",
      "control",
      "monitor",
      "platform",
      "vision_voice",
      "navigation",
      "lifecycle",
      "decision",
      "frontend"
    ],
    "capabilityMatrix": {
      "voice": true,
      "vision": true,
      "monitor": true,
      "teleop": true,
      "localization": true,
      "navigation": true,
      "hardware_interface": true,
      "api_server": true,
      "web_bridge": true,
      "mock_robot": false,
      "debug_overlay": true,
      "diagnostics": true,
      "preflight_checks": true
    },
    "surfaceContract": {
      "backend": {
        "enabled": true,
        "required_nodes": [
          "robot_decision",
          "robot_control",
          "robot_bridge"
        ],
        "ready_topics": [],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "web_bridge": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "frontend": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [
          "http://127.0.0.1:9100/api/v1/health"
        ],
        "require_operator_ready": true
      }
    }
  },
  "hardware": {
    "profileName": "hardware",
    "profile": {
      "name": "hardware",
      "enable_voice": true,
      "enable_vision": true,
      "enable_monitor": true,
      "enable_teleop": true,
      "enable_localization": true,
      "enable_navigation": true,
      "enable_hardware_interface": true,
      "enable_api_server": true,
      "log_level": "info",
      "use_mock_robot": false,
      "enable_debug_overlay": false,
      "diagnostics_enabled": true,
      "enable_web_bridge": true,
      "preflight_checks_enabled": true,
      "bridge_host": "192.168.4.1",
      "bridge_port": 9000,
      "mjpeg_url": "http://192.168.4.1:81/stream",
      "websocket_public_host": "192.168.4.1",
      "websocket_listen_host": "127.0.0.1",
      "websocket_port": 9001,
      "websocket_path": "/ws",
      "api_server_public_host": "127.0.0.1",
      "api_server_listen_host": "127.0.0.1",
      "api_server_port": 9100,
      "api_server_ws_path": "/ws",
      "api_server_api_prefix": "/api/v1",
      "description": "真实机器人运行配置，侧重稳定性。",
      "tags": [
        "hardware",
        "stable"
      ],
      "enabled_nodes": [
        "robot_decision",
        "robot_control",
        "robot_bridge",
        "robot_voice",
        "robot_vision",
        "robot_monitor",
        "robot_teleop",
        "robot_web_bridge",
        "robot_localization",
        "robot_navigation",
        "robot_hardware_interface",
        "robot_api_server"
      ],
      "feature_matrix": {
        "voice": true,
        "vision": true,
        "monitor": true,
        "teleop": true,
        "mock_robot": false,
        "debug_overlay": false,
        "diagnostics": true,
        "web_bridge": true,
        "localization": true,
        "navigation": true,
        "hardware_interface": true,
        "api_server": true,
        "preflight_checks": true
      },
      "runtime": {
        "mock_enabled": false,
        "bridge": {
          "host": "192.168.4.1",
          "port": 9000,
          "mjpeg_url": "http://192.168.4.1:81/stream"
        },
        "web_bridge_enabled": true
      },
      "operational_class": "hardware_stable",
      "deployment_tier": "real_robot",
      "hardware_boundary_mode": "ubuntu_runtime_plus_board_boundary_contract",
      "startup_sequence": [
        "contracts",
        "bridge",
        "control",
        "monitor",
        "platform",
        "vision_voice",
        "navigation",
        "lifecycle",
        "decision",
        "frontend"
      ],
      "runtime_supervision": {
        "startupBarrierEnabled": true,
        "startupBarrierPhases": [
          "contracts",
          "bridge",
          "control",
          "monitor",
          "platform",
          "vision_voice",
          "navigation",
          "lifecycle",
          "decision",
          "frontend"
        ],
        "runtimeHealthSurface": "connection.runtimeHealthState/runtimeHealthReasons",
        "startupReadinessSurface": "/robot/web_bridge/ready",
        "supervisionMode": "startup_barrier_plus_ros_lifecycle_manager",
        "operatorSurfaceContract": {
          "enabled": true,
          "required_nodes": [
            "robot_web_bridge"
          ],
          "ready_topics": [
            "/robot/web_bridge/ready"
          ],
          "ready_http_urls": [
            "http://127.0.0.1:9100/api/v1/health"
          ],
          "require_operator_ready": true
        },
        "surfaceMatrix": {
          "backend": {
            "enabled": true,
            "required_nodes": [
              "robot_decision",
              "robot_control",
              "robot_bridge"
            ],
            "ready_topics": [],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "web_bridge": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "frontend": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [
              "http://127.0.0.1:9100/api/v1/health"
            ],
            "require_operator_ready": true
          }
        },
        "failureTaxonomy": {
          "startup": {
            "missing_node": {
              "severity": "fatal",
              "operator_action": "inspect_launch_and_process_logs"
            },
            "missing_ready_topic": {
              "severity": "fatal",
              "operator_action": "wait_for_startup_barrier_or_restart_surface"
            },
            "missing_http_probe": {
              "severity": "fatal",
              "operator_action": "inspect_api_server_or_surface_health_endpoint"
            },
            "preflight_failed": {
              "severity": "fatal",
              "operator_action": "resolve_reported_dependency_or_config_gap"
            }
          },
          "runtime": {
            "bridge_runtime_degraded": {
              "severity": "warn",
              "operator_action": "inspect_runtime_health_reasons_and_transport_stats"
            },
            "operator_surface_unready": {
              "severity": "warn",
              "operator_action": "check_websocket_gateway_and_frontend_connectivity"
            },
            "api_surface_unready": {
              "severity": "warn",
              "operator_action": "inspect_api_server_runtime_health_and_operator_ready_reasons"
            },
            "runtime_param_timeout": {
              "severity": "warn",
              "operator_action": "inspect_consumer_status_and_retry_or_rollback"
            }
          }
        },
        "runtimeSupervisorPresent": true,
        "lifecycleManagerPresent": true,
        "lifecycleManagerType": "ros_lifecycle_manager",
        "bondSupervisionPresent": true,
        "bondSupervisionType": "bondpy_supervision",
        "recoveryMode": "ros_lifecycle_manager_safe_shutdown_and_manual_reactivate",
        "runtimeSupervisionTopic": "/robot/runtime/supervision",
        "runtimeOrchestrationTopic": "/robot/runtime/orchestration",
        "runtimeOrchestrationReadyTopic": "/robot/runtime/orchestration/ready",
        "runtimeLifecycleSurface": "/robot/lifecycle_manager/status.lifecycleManager",
        "runtimeBondSurface": "/robot/lifecycle_manager/status.bondSupervision",
        "runtimeRecoveryPlanSurface": "/robot/lifecycle_manager/status.recoveryPlan",
        "lifecycleManagerStatusTopic": "/robot/lifecycle_manager/status",
        "lifecycleManagerReadyTopic": "/robot/lifecycle_manager/ready",
        "notes": [
          "startup barrier readiness and runtime supervision are modeled separately so startup success is not mistaken for runtime stability",
          "operator surface readiness requires the web bridge ready topic and the API health contract when API server is enabled",
          "the bringup stack now launches ROS lifecycle wrapper nodes and a ROS lifecycle manager that configures and activates managed components through lifecycle_msgs services",
          "bond supervision is provided by bondpy on the ROS bond topic and lifecycle degradation is surfaced through /robot/lifecycle_manager/status",
          "localization/hardware-interface/api-server remain optional per profile and are reported through the supervision component map when the monitor is enabled",
          "runtime supervisor publishes /robot/runtime/supervision and embeds authoritative lifecycleManager / bondSupervision / recoveryPlan sections from the ROS lifecycle manager status topic",
          "runtime orchestration manager publishes /robot/runtime/orchestration and /robot/runtime/orchestration/ready so startup, pause, recovery, degraded, and shutdown phases share one bringup-level state machine"
        ]
      }
    },
    "startupSequence": [
      "contracts",
      "bridge",
      "control",
      "monitor",
      "platform",
      "vision_voice",
      "navigation",
      "lifecycle",
      "decision",
      "frontend"
    ],
    "capabilityMatrix": {
      "voice": true,
      "vision": true,
      "monitor": true,
      "teleop": true,
      "localization": true,
      "navigation": true,
      "hardware_interface": true,
      "api_server": true,
      "web_bridge": true,
      "mock_robot": false,
      "debug_overlay": false,
      "diagnostics": true,
      "preflight_checks": true
    },
    "surfaceContract": {
      "backend": {
        "enabled": true,
        "required_nodes": [
          "robot_decision",
          "robot_control",
          "robot_bridge"
        ],
        "ready_topics": [],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "web_bridge": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "frontend": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [
          "http://127.0.0.1:9100/api/v1/health"
        ],
        "require_operator_ready": true
      }
    }
  },
  "minimal": {
    "profileName": "minimal",
    "profile": {
      "name": "minimal",
      "enable_voice": false,
      "enable_vision": false,
      "enable_monitor": false,
      "enable_teleop": false,
      "enable_localization": true,
      "enable_navigation": false,
      "enable_hardware_interface": true,
      "enable_api_server": false,
      "log_level": "warn",
      "use_mock_robot": true,
      "enable_debug_overlay": false,
      "diagnostics_enabled": false,
      "enable_web_bridge": false,
      "preflight_checks_enabled": true,
      "bridge_host": null,
      "bridge_port": null,
      "mjpeg_url": null,
      "websocket_public_host": null,
      "websocket_listen_host": null,
      "websocket_port": 9001,
      "websocket_path": "/ws",
      "api_server_public_host": null,
      "api_server_listen_host": null,
      "api_server_port": 9100,
      "api_server_ws_path": "/ws",
      "api_server_api_prefix": "/api/v1",
      "description": "最小链路，仅验证 ROS2->bridge->底盘控制主通路。",
      "tags": [
        "ci",
        "smoke"
      ],
      "enabled_nodes": [
        "robot_decision",
        "robot_control",
        "robot_bridge",
        "robot_localization",
        "robot_hardware_interface"
      ],
      "feature_matrix": {
        "voice": false,
        "vision": false,
        "monitor": false,
        "teleop": false,
        "mock_robot": true,
        "debug_overlay": false,
        "diagnostics": false,
        "web_bridge": false,
        "localization": true,
        "navigation": false,
        "hardware_interface": true,
        "api_server": false,
        "preflight_checks": true
      },
      "runtime": {
        "mock_enabled": true,
        "bridge": {
          "host": "127.0.0.1",
          "port": 9000,
          "mjpeg_url": null
        },
        "web_bridge_enabled": false
      },
      "operational_class": "mock",
      "deployment_tier": "host_harness",
      "hardware_boundary_mode": "host_harness_only",
      "startup_sequence": [
        "contracts",
        "bridge",
        "control",
        "platform",
        "lifecycle",
        "decision"
      ],
      "runtime_supervision": {
        "startupBarrierEnabled": true,
        "startupBarrierPhases": [
          "contracts",
          "bridge",
          "control",
          "platform",
          "lifecycle",
          "decision"
        ],
        "runtimeHealthSurface": "connection.runtimeHealthState/runtimeHealthReasons",
        "startupReadinessSurface": null,
        "supervisionMode": "startup_barrier_plus_ros_lifecycle_manager_without_monitor",
        "operatorSurfaceContract": {
          "enabled": false,
          "required_nodes": [
            "robot_web_bridge"
          ],
          "ready_topics": [
            "/robot/web_bridge/ready"
          ],
          "ready_http_urls": [
            "http://127.0.0.1:9100/api/v1/health"
          ],
          "require_operator_ready": true
        },
        "surfaceMatrix": {
          "backend": {
            "enabled": true,
            "required_nodes": [
              "robot_decision",
              "robot_control",
              "robot_bridge"
            ],
            "ready_topics": [],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "web_bridge": {
            "enabled": false,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "frontend": {
            "enabled": false,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [
              "http://127.0.0.1:9100/api/v1/health"
            ],
            "require_operator_ready": true
          }
        },
        "failureTaxonomy": {
          "startup": {
            "missing_node": {
              "severity": "fatal",
              "operator_action": "inspect_launch_and_process_logs"
            },
            "missing_ready_topic": {
              "severity": "fatal",
              "operator_action": "wait_for_startup_barrier_or_restart_surface"
            },
            "missing_http_probe": {
              "severity": "fatal",
              "operator_action": "inspect_api_server_or_surface_health_endpoint"
            },
            "preflight_failed": {
              "severity": "fatal",
              "operator_action": "resolve_reported_dependency_or_config_gap"
            }
          },
          "runtime": {
            "bridge_runtime_degraded": {
              "severity": "warn",
              "operator_action": "inspect_runtime_health_reasons_and_transport_stats"
            },
            "operator_surface_unready": {
              "severity": "warn",
              "operator_action": "check_websocket_gateway_and_frontend_connectivity"
            },
            "api_surface_unready": {
              "severity": "warn",
              "operator_action": "inspect_api_server_runtime_health_and_operator_ready_reasons"
            },
            "runtime_param_timeout": {
              "severity": "warn",
              "operator_action": "inspect_consumer_status_and_retry_or_rollback"
            }
          }
        },
        "runtimeSupervisorPresent": false,
        "lifecycleManagerPresent": true,
        "lifecycleManagerType": "ros_lifecycle_manager",
        "bondSupervisionPresent": true,
        "bondSupervisionType": "bondpy_supervision",
        "recoveryMode": "ros_lifecycle_manager_safe_shutdown_and_manual_reactivate",
        "runtimeSupervisionTopic": null,
        "runtimeOrchestrationTopic": null,
        "runtimeOrchestrationReadyTopic": null,
        "runtimeLifecycleSurface": "/robot/lifecycle_manager/status.lifecycleManager",
        "runtimeBondSurface": "/robot/lifecycle_manager/status.bondSupervision",
        "runtimeRecoveryPlanSurface": "/robot/lifecycle_manager/status.recoveryPlan",
        "lifecycleManagerStatusTopic": "/robot/lifecycle_manager/status",
        "lifecycleManagerReadyTopic": "/robot/lifecycle_manager/ready",
        "notes": [
          "startup barrier readiness and runtime supervision are modeled separately so startup success is not mistaken for runtime stability",
          "operator surface readiness requires the web bridge ready topic and the API health contract when API server is enabled",
          "the bringup stack now launches ROS lifecycle wrapper nodes and a ROS lifecycle manager that configures and activates managed components through lifecycle_msgs services",
          "bond supervision is provided by bondpy on the ROS bond topic and lifecycle degradation is surfaced through /robot/lifecycle_manager/status",
          "localization/hardware-interface/api-server remain optional per profile and are reported through the supervision component map when the monitor is enabled",
          "runtime supervision topic is absent when the monitor is disabled; lifecycle manager and bond supervision remain available directly on /robot/lifecycle_manager/status"
        ]
      }
    },
    "startupSequence": [
      "contracts",
      "bridge",
      "control",
      "platform",
      "lifecycle",
      "decision"
    ],
    "capabilityMatrix": {
      "voice": false,
      "vision": false,
      "monitor": false,
      "teleop": false,
      "localization": true,
      "navigation": false,
      "hardware_interface": true,
      "api_server": false,
      "web_bridge": false,
      "mock_robot": true,
      "debug_overlay": false,
      "diagnostics": false,
      "preflight_checks": true
    },
    "surfaceContract": {
      "backend": {
        "enabled": true,
        "required_nodes": [
          "robot_decision",
          "robot_control",
          "robot_bridge"
        ],
        "ready_topics": [],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "web_bridge": {
        "enabled": false,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "frontend": {
        "enabled": false,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [
          "http://127.0.0.1:9100/api/v1/health"
        ],
        "require_operator_ready": true
      }
    }
  },
  "mock": {
    "profileName": "mock",
    "profile": {
      "name": "mock",
      "enable_voice": true,
      "enable_vision": true,
      "enable_monitor": true,
      "enable_teleop": true,
      "enable_localization": true,
      "enable_navigation": true,
      "enable_hardware_interface": true,
      "enable_api_server": true,
      "log_level": "debug",
      "use_mock_robot": true,
      "enable_debug_overlay": true,
      "diagnostics_enabled": true,
      "enable_web_bridge": true,
      "preflight_checks_enabled": true,
      "bridge_host": "127.0.0.1",
      "bridge_port": 9000,
      "mjpeg_url": "http://127.0.0.1:8080/stream",
      "websocket_public_host": "127.0.0.1",
      "websocket_listen_host": "127.0.0.1",
      "websocket_port": 9001,
      "websocket_path": "/ws",
      "api_server_public_host": "127.0.0.1",
      "api_server_listen_host": "127.0.0.1",
      "api_server_port": 9100,
      "api_server_ws_path": "/ws",
      "api_server_api_prefix": "/api/v1",
      "description": "本地仿真配置，自动启动 TCP mock 机器人。",
      "tags": [
        "mock",
        "regression"
      ],
      "enabled_nodes": [
        "robot_decision",
        "robot_control",
        "robot_bridge",
        "robot_voice",
        "robot_vision",
        "robot_monitor",
        "robot_teleop",
        "robot_web_bridge",
        "robot_localization",
        "robot_navigation",
        "robot_hardware_interface",
        "robot_api_server"
      ],
      "feature_matrix": {
        "voice": true,
        "vision": true,
        "monitor": true,
        "teleop": true,
        "mock_robot": true,
        "debug_overlay": true,
        "diagnostics": true,
        "web_bridge": true,
        "localization": true,
        "navigation": true,
        "hardware_interface": true,
        "api_server": true,
        "preflight_checks": true
      },
      "runtime": {
        "mock_enabled": true,
        "bridge": {
          "host": "127.0.0.1",
          "port": 9000,
          "mjpeg_url": "http://127.0.0.1:8080/stream"
        },
        "web_bridge_enabled": true
      },
      "operational_class": "mock",
      "deployment_tier": "host_harness",
      "hardware_boundary_mode": "host_harness_only",
      "startup_sequence": [
        "contracts",
        "bridge",
        "control",
        "monitor",
        "platform",
        "vision_voice",
        "navigation",
        "lifecycle",
        "decision",
        "frontend"
      ],
      "runtime_supervision": {
        "startupBarrierEnabled": true,
        "startupBarrierPhases": [
          "contracts",
          "bridge",
          "control",
          "monitor",
          "platform",
          "vision_voice",
          "navigation",
          "lifecycle",
          "decision",
          "frontend"
        ],
        "runtimeHealthSurface": "connection.runtimeHealthState/runtimeHealthReasons",
        "startupReadinessSurface": "/robot/web_bridge/ready",
        "supervisionMode": "startup_barrier_plus_ros_lifecycle_manager",
        "operatorSurfaceContract": {
          "enabled": true,
          "required_nodes": [
            "robot_web_bridge"
          ],
          "ready_topics": [
            "/robot/web_bridge/ready"
          ],
          "ready_http_urls": [
            "http://127.0.0.1:9100/api/v1/health"
          ],
          "require_operator_ready": true
        },
        "surfaceMatrix": {
          "backend": {
            "enabled": true,
            "required_nodes": [
              "robot_decision",
              "robot_control",
              "robot_bridge"
            ],
            "ready_topics": [],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "web_bridge": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "frontend": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [
              "http://127.0.0.1:9100/api/v1/health"
            ],
            "require_operator_ready": true
          }
        },
        "failureTaxonomy": {
          "startup": {
            "missing_node": {
              "severity": "fatal",
              "operator_action": "inspect_launch_and_process_logs"
            },
            "missing_ready_topic": {
              "severity": "fatal",
              "operator_action": "wait_for_startup_barrier_or_restart_surface"
            },
            "missing_http_probe": {
              "severity": "fatal",
              "operator_action": "inspect_api_server_or_surface_health_endpoint"
            },
            "preflight_failed": {
              "severity": "fatal",
              "operator_action": "resolve_reported_dependency_or_config_gap"
            }
          },
          "runtime": {
            "bridge_runtime_degraded": {
              "severity": "warn",
              "operator_action": "inspect_runtime_health_reasons_and_transport_stats"
            },
            "operator_surface_unready": {
              "severity": "warn",
              "operator_action": "check_websocket_gateway_and_frontend_connectivity"
            },
            "api_surface_unready": {
              "severity": "warn",
              "operator_action": "inspect_api_server_runtime_health_and_operator_ready_reasons"
            },
            "runtime_param_timeout": {
              "severity": "warn",
              "operator_action": "inspect_consumer_status_and_retry_or_rollback"
            }
          }
        },
        "runtimeSupervisorPresent": true,
        "lifecycleManagerPresent": true,
        "lifecycleManagerType": "ros_lifecycle_manager",
        "bondSupervisionPresent": true,
        "bondSupervisionType": "bondpy_supervision",
        "recoveryMode": "ros_lifecycle_manager_safe_shutdown_and_manual_reactivate",
        "runtimeSupervisionTopic": "/robot/runtime/supervision",
        "runtimeOrchestrationTopic": "/robot/runtime/orchestration",
        "runtimeOrchestrationReadyTopic": "/robot/runtime/orchestration/ready",
        "runtimeLifecycleSurface": "/robot/lifecycle_manager/status.lifecycleManager",
        "runtimeBondSurface": "/robot/lifecycle_manager/status.bondSupervision",
        "runtimeRecoveryPlanSurface": "/robot/lifecycle_manager/status.recoveryPlan",
        "lifecycleManagerStatusTopic": "/robot/lifecycle_manager/status",
        "lifecycleManagerReadyTopic": "/robot/lifecycle_manager/ready",
        "notes": [
          "startup barrier readiness and runtime supervision are modeled separately so startup success is not mistaken for runtime stability",
          "operator surface readiness requires the web bridge ready topic and the API health contract when API server is enabled",
          "the bringup stack now launches ROS lifecycle wrapper nodes and a ROS lifecycle manager that configures and activates managed components through lifecycle_msgs services",
          "bond supervision is provided by bondpy on the ROS bond topic and lifecycle degradation is surfaced through /robot/lifecycle_manager/status",
          "localization/hardware-interface/api-server remain optional per profile and are reported through the supervision component map when the monitor is enabled",
          "runtime supervisor publishes /robot/runtime/supervision and embeds authoritative lifecycleManager / bondSupervision / recoveryPlan sections from the ROS lifecycle manager status topic",
          "runtime orchestration manager publishes /robot/runtime/orchestration and /robot/runtime/orchestration/ready so startup, pause, recovery, degraded, and shutdown phases share one bringup-level state machine"
        ]
      }
    },
    "startupSequence": [
      "contracts",
      "bridge",
      "control",
      "monitor",
      "platform",
      "vision_voice",
      "navigation",
      "lifecycle",
      "decision",
      "frontend"
    ],
    "capabilityMatrix": {
      "voice": true,
      "vision": true,
      "monitor": true,
      "teleop": true,
      "localization": true,
      "navigation": true,
      "hardware_interface": true,
      "api_server": true,
      "web_bridge": true,
      "mock_robot": true,
      "debug_overlay": true,
      "diagnostics": true,
      "preflight_checks": true
    },
    "surfaceContract": {
      "backend": {
        "enabled": true,
        "required_nodes": [
          "robot_decision",
          "robot_control",
          "robot_bridge"
        ],
        "ready_topics": [],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "web_bridge": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "frontend": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [
          "http://127.0.0.1:9100/api/v1/health"
        ],
        "require_operator_ready": true
      }
    }
  },
  "sim": {
    "profileName": "sim",
    "profile": {
      "name": "sim",
      "enable_voice": true,
      "enable_vision": true,
      "enable_monitor": true,
      "enable_teleop": true,
      "enable_localization": true,
      "enable_navigation": true,
      "enable_hardware_interface": true,
      "enable_api_server": true,
      "log_level": "debug",
      "use_mock_robot": false,
      "enable_debug_overlay": true,
      "diagnostics_enabled": true,
      "enable_web_bridge": true,
      "preflight_checks_enabled": true,
      "bridge_host": "127.0.0.1",
      "bridge_port": 9000,
      "mjpeg_url": "http://127.0.0.1:8080/stream",
      "websocket_public_host": "127.0.0.1",
      "websocket_listen_host": "127.0.0.1",
      "websocket_port": 9001,
      "websocket_path": "/ws",
      "api_server_public_host": "127.0.0.1",
      "api_server_listen_host": "127.0.0.1",
      "api_server_port": 9100,
      "api_server_ws_path": "/ws",
      "api_server_api_prefix": "/api/v1",
      "description": "ROS 侧仿真配置，使用 in-repo simulator 代替 TCP mock robot。",
      "tags": [
        "sim",
        "regression"
      ],
      "enabled_nodes": [
        "robot_decision",
        "robot_control",
        "robot_bridge",
        "robot_voice",
        "robot_vision",
        "robot_monitor",
        "robot_teleop",
        "robot_web_bridge",
        "robot_localization",
        "robot_navigation",
        "robot_hardware_interface",
        "robot_api_server"
      ],
      "feature_matrix": {
        "voice": true,
        "vision": true,
        "monitor": true,
        "teleop": true,
        "mock_robot": false,
        "debug_overlay": true,
        "diagnostics": true,
        "web_bridge": true,
        "localization": true,
        "navigation": true,
        "hardware_interface": true,
        "api_server": true,
        "preflight_checks": true
      },
      "runtime": {
        "mock_enabled": false,
        "bridge": {
          "host": "127.0.0.1",
          "port": 9000,
          "mjpeg_url": "http://127.0.0.1:8080/stream"
        },
        "web_bridge_enabled": true
      },
      "operational_class": "hardware_debug",
      "deployment_tier": "host_harness",
      "hardware_boundary_mode": "host_harness_only",
      "startup_sequence": [
        "contracts",
        "bridge",
        "control",
        "monitor",
        "platform",
        "vision_voice",
        "navigation",
        "lifecycle",
        "decision",
        "frontend"
      ],
      "runtime_supervision": {
        "startupBarrierEnabled": true,
        "startupBarrierPhases": [
          "contracts",
          "bridge",
          "control",
          "monitor",
          "platform",
          "vision_voice",
          "navigation",
          "lifecycle",
          "decision",
          "frontend"
        ],
        "runtimeHealthSurface": "connection.runtimeHealthState/runtimeHealthReasons",
        "startupReadinessSurface": "/robot/web_bridge/ready",
        "supervisionMode": "startup_barrier_plus_ros_lifecycle_manager",
        "operatorSurfaceContract": {
          "enabled": true,
          "required_nodes": [
            "robot_web_bridge"
          ],
          "ready_topics": [
            "/robot/web_bridge/ready"
          ],
          "ready_http_urls": [
            "http://127.0.0.1:9100/api/v1/health"
          ],
          "require_operator_ready": true
        },
        "surfaceMatrix": {
          "backend": {
            "enabled": true,
            "required_nodes": [
              "robot_decision",
              "robot_control",
              "robot_bridge"
            ],
            "ready_topics": [],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "web_bridge": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [],
            "require_operator_ready": false
          },
          "frontend": {
            "enabled": true,
            "required_nodes": [
              "robot_web_bridge"
            ],
            "ready_topics": [
              "/robot/web_bridge/ready"
            ],
            "ready_http_urls": [
              "http://127.0.0.1:9100/api/v1/health"
            ],
            "require_operator_ready": true
          }
        },
        "failureTaxonomy": {
          "startup": {
            "missing_node": {
              "severity": "fatal",
              "operator_action": "inspect_launch_and_process_logs"
            },
            "missing_ready_topic": {
              "severity": "fatal",
              "operator_action": "wait_for_startup_barrier_or_restart_surface"
            },
            "missing_http_probe": {
              "severity": "fatal",
              "operator_action": "inspect_api_server_or_surface_health_endpoint"
            },
            "preflight_failed": {
              "severity": "fatal",
              "operator_action": "resolve_reported_dependency_or_config_gap"
            }
          },
          "runtime": {
            "bridge_runtime_degraded": {
              "severity": "warn",
              "operator_action": "inspect_runtime_health_reasons_and_transport_stats"
            },
            "operator_surface_unready": {
              "severity": "warn",
              "operator_action": "check_websocket_gateway_and_frontend_connectivity"
            },
            "api_surface_unready": {
              "severity": "warn",
              "operator_action": "inspect_api_server_runtime_health_and_operator_ready_reasons"
            },
            "runtime_param_timeout": {
              "severity": "warn",
              "operator_action": "inspect_consumer_status_and_retry_or_rollback"
            }
          }
        },
        "runtimeSupervisorPresent": true,
        "lifecycleManagerPresent": true,
        "lifecycleManagerType": "ros_lifecycle_manager",
        "bondSupervisionPresent": true,
        "bondSupervisionType": "bondpy_supervision",
        "recoveryMode": "ros_lifecycle_manager_safe_shutdown_and_manual_reactivate",
        "runtimeSupervisionTopic": "/robot/runtime/supervision",
        "runtimeOrchestrationTopic": "/robot/runtime/orchestration",
        "runtimeOrchestrationReadyTopic": "/robot/runtime/orchestration/ready",
        "runtimeLifecycleSurface": "/robot/lifecycle_manager/status.lifecycleManager",
        "runtimeBondSurface": "/robot/lifecycle_manager/status.bondSupervision",
        "runtimeRecoveryPlanSurface": "/robot/lifecycle_manager/status.recoveryPlan",
        "lifecycleManagerStatusTopic": "/robot/lifecycle_manager/status",
        "lifecycleManagerReadyTopic": "/robot/lifecycle_manager/ready",
        "notes": [
          "startup barrier readiness and runtime supervision are modeled separately so startup success is not mistaken for runtime stability",
          "operator surface readiness requires the web bridge ready topic and the API health contract when API server is enabled",
          "the bringup stack now launches ROS lifecycle wrapper nodes and a ROS lifecycle manager that configures and activates managed components through lifecycle_msgs services",
          "bond supervision is provided by bondpy on the ROS bond topic and lifecycle degradation is surfaced through /robot/lifecycle_manager/status",
          "localization/hardware-interface/api-server remain optional per profile and are reported through the supervision component map when the monitor is enabled",
          "runtime supervisor publishes /robot/runtime/supervision and embeds authoritative lifecycleManager / bondSupervision / recoveryPlan sections from the ROS lifecycle manager status topic",
          "runtime orchestration manager publishes /robot/runtime/orchestration and /robot/runtime/orchestration/ready so startup, pause, recovery, degraded, and shutdown phases share one bringup-level state machine"
        ]
      }
    },
    "startupSequence": [
      "contracts",
      "bridge",
      "control",
      "monitor",
      "platform",
      "vision_voice",
      "navigation",
      "lifecycle",
      "decision",
      "frontend"
    ],
    "capabilityMatrix": {
      "voice": true,
      "vision": true,
      "monitor": true,
      "teleop": true,
      "localization": true,
      "navigation": true,
      "hardware_interface": true,
      "api_server": true,
      "web_bridge": true,
      "mock_robot": false,
      "debug_overlay": true,
      "diagnostics": true,
      "preflight_checks": true
    },
    "surfaceContract": {
      "backend": {
        "enabled": true,
        "required_nodes": [
          "robot_decision",
          "robot_control",
          "robot_bridge"
        ],
        "ready_topics": [],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "web_bridge": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [],
        "require_operator_ready": false
      },
      "frontend": {
        "enabled": true,
        "required_nodes": [
          "robot_web_bridge"
        ],
        "ready_topics": [
          "/robot/web_bridge/ready"
        ],
        "ready_http_urls": [
          "http://127.0.0.1:9100/api/v1/health"
        ],
        "require_operator_ready": true
      }
    }
  }
} as const;

        export const capabilityRegistrySchema = z.record(z.string(), z.object({
          capabilityId: z.string(),
          title: z.string(),
          domain: z.string(),
          implementationStatus: z.string(),
          governanceStage: z.string(),
          acceptanceStage: z.string(),
          uiExposurePolicy: z.string(),
          frontendMaturity: z.string(),
          releaseNotePolicy: z.string(),
          truthSourcePaths: z.array(z.string()),
          evidenceArtifacts: z.array(z.string()),
          externalDependencies: z.array(z.string()),
          entrySurfaces: z.array(z.string()),
          runtimeClaims: z.array(z.string()),
          nonClaims: z.array(z.string()),
          operatorNotes: z.array(z.string()),
        }));

        export const laneRegistrySchema = z.record(z.string(), z.object({
          laneId: z.string(),
          capabilityId: z.string().nullable(),
          domain: z.string(),
          owner: z.string(),
          packageName: z.string(),
          executable: z.string(),
          childFactory: z.string(),
          activationDecision: z.string(),
          rollbackPolicy: z.string(),
          evidenceRequired: z.array(z.string()),
          upgradeCondition: z.string(),
          description: z.string(),
          visibility: z.string(),
          lifecycleStage: z.string(),
          defaultSurfaceExposure: z.string(),
          retentionCondition: z.string(),
          exitCondition: z.string(),
        }));

        export const governanceSignalEntrySchema = z.object({
          kind: z.string(),
          producer: z.string(),
          runtimeConsumers: z.array(z.string()).optional(),
          uiConsumers: z.array(z.string()).optional(),
          evidenceConsumers: z.array(z.string()).optional(),
          ackOwners: z.array(z.string()).optional(),
          notes: z.string().optional(),
          scope: z.string().optional(),
          evidenceLayer: z.string(),
          machineEvidenceAllowed: z.boolean(),
        });

        export const governanceSignalRegistrySchema = z.object({
          topics: z.record(z.string(), governanceSignalEntrySchema),
          commands: z.record(z.string(), governanceSignalEntrySchema),
          runtimeParameters: z.record(z.string(), governanceSignalEntrySchema),
          reports: z.record(z.string(), governanceSignalEntrySchema),
          validationErrors: z.array(z.string()),
        });

        export const featureAdmissionEntrySchema = z.object({
          featureId: z.string(),
          capabilityIds: z.array(z.string()),
          title: z.string(),
          maturity: z.string(),
          entrySurfaces: z.array(z.string()),
          commands: z.array(z.string()),
          authoritativeNodes: z.array(z.string()),
          runtimeProducers: z.array(z.string()),
          runtimeConsumers: z.array(z.string()),
          uiConsumers: z.array(z.string()),
          configPaths: z.array(z.string()),
          verificationTargets: z.array(z.string()),
          acceptanceArtifacts: z.array(z.string()),
          rollbackPaths: z.array(z.string()),
          externalDependencies: z.array(z.string()),
          nonClaims: z.array(z.string()),
          operatorNotes: z.array(z.string()),
        });

        export const featureAdmissionRegistrySchema = z.record(z.string(), featureAdmissionEntrySchema);

        export const commandRouteEntrySchema = z.object({
          commandType: z.string(),
          entrySurfaces: z.array(z.string()),
          sessionPolicy: z.string(),
          dispatchTransport: z.string(),
          bridgeHandler: z.string(),
          targetNodes: z.array(z.string()),
          timeoutBudgetMs: z.number(),
          fallbackPaths: z.array(z.string()),
          denyConditions: z.array(z.string()),
          rollbackPaths: z.array(z.string()),
          allowedModes: z.array(z.string()),
          targetMode: z.string().nullable(),
          terminalLifecycleStatuses: z.array(z.string()),
          notes: z.array(z.string()),
        });
        export const commandRouteRegistrySchema = z.record(z.string(), commandRouteEntrySchema);

        export const surfaceRegistryEntrySchema = z.object({
          surfaceId: z.string(),
          surfaceLayers: z.array(z.string()),
          authorityModel: z.string(),
          defaultTransport: z.string(),
          writeEnabled: z.boolean(),
          machineGateAllowed: z.boolean(),
          truthSourcePaths: z.array(z.string()),
          notes: z.array(z.string()),
        });
        export const surfaceRegistrySchema = z.record(z.string(), surfaceRegistryEntrySchema);

        export const runtimeOrchestrationEntrySchema = z.object({
          componentId: z.string(),
          reportKey: z.string(),
          requiredForMainline: z.boolean(),
          runtimeTopics: z.array(z.string()),
          operatorVisibleFields: z.array(z.string()),
          truthSourcePaths: z.array(z.string()),
          recoveryOwner: z.string(),
          notes: z.array(z.string()),
        });
        export const runtimeOrchestrationRegistrySchema = z.record(z.string(), runtimeOrchestrationEntrySchema);

        export const navigationAdapterBoundaryEntrySchema = z.object({
          laneId: z.string(),
          providerName: z.string(),
          boundaryRole: z.string(),
          packageName: z.string(),
          executable: z.string(),
          adapterRuntime: z.boolean(),
          defaultMainline: z.boolean(),
          promotionChecklist: z.array(z.string()),
          rollbackBaseline: z.string(),
          nonClaims: z.array(z.string()),
          truthSourcePaths: z.array(z.string()),
        });
        export const navigationAdapterBoundaryRegistrySchema = z.record(z.string(), navigationAdapterBoundaryEntrySchema);

        export const releaseGateEntrySchema = z.object({
          gateId: z.string(),
          title: z.string(),
          scriptPaths: z.array(z.string()),
          stage: z.string(),
          blockingByDefault: z.boolean(),
          notes: z.array(z.string()),
        });
        export const releaseGateRegistrySchema = z.record(z.string(), releaseGateEntrySchema);

        export const profileRegistryEntrySchema = z.object({
          profileName: z.string(),
          profile: z.record(z.string(), z.unknown()),
          startupSequence: z.array(z.string()),
          capabilityMatrix: z.record(z.string(), z.boolean()),
          surfaceContract: z.record(z.string(), z.object({
            enabled: z.boolean(),
            required_nodes: z.array(z.string()),
            ready_topics: z.array(z.string()),
            ready_http_urls: z.array(z.string()),
            require_operator_ready: z.boolean(),
          })),
        });
        export const profileRegistrySchema = z.record(z.string(), profileRegistryEntrySchema);

        export type GeneratedCapabilityRegistry = typeof capabilityRegistry;
        export type GeneratedLaneRegistry = typeof laneRegistry;
        export type GeneratedSignalRegistry = typeof signalRegistry;
        export type GeneratedFeatureAdmissionRegistry = typeof featureAdmissionRegistry;
        export type GeneratedCommandRouteRegistry = typeof commandRouteRegistry;
        export type GeneratedSurfaceRegistry = typeof surfaceRegistry;
        export type GeneratedRuntimeOrchestrationRegistry = typeof runtimeOrchestrationRegistry;
        export type GeneratedNavigationAdapterBoundaryRegistry = typeof navigationAdapterBoundaryRegistry;
        export type GeneratedReleaseGateRegistry = typeof releaseGateRegistry;
        export type GeneratedProfileRegistry = typeof profileRegistry;
