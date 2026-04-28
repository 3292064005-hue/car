from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from robot_contracts.bridge_contract import COMMAND_TYPES
from robot_contracts.capability_registry import get_capability_entry
from robot_contracts.surface_registry import surface_registry_payload


_FEATURE_TO_CAPABILITIES: dict[str, tuple[str, ...]] = {
    'operator.mode_switch': ('operator.mode_switch',),
    'operator.teleop_control': ('operator.teleop_control',),
    'operator.safety_recovery': ('operator.safety_recovery',),
    'operator.patrol_execution': ('operator.patrol_execution', 'navigation.simple_nav_provider', 'navigation.nav2_provider'),
    'operator.runtime_param_commit': ('operator.runtime_param_commit',),
    'operator.voice_fixed_text': ('operator.voice_fixed_text',),
    'operator.snapshot_capture': ('operator.snapshot_capture',),
    'observability.runtime_reports': ('observability.runtime_reports',),
    'observability.system_replay_evidence': ('observability.system_replay_evidence',),
}


@dataclass(frozen=True)
class FeatureAdmissionEntry:
    feature_id: str
    capability_ids: tuple[str, ...]
    title: str
    maturity: str
    entry_surfaces: tuple[str, ...]
    commands: tuple[str, ...]
    authoritative_nodes: tuple[str, ...]
    runtime_producers: tuple[str, ...]
    runtime_consumers: tuple[str, ...]
    ui_consumers: tuple[str, ...]
    config_paths: tuple[str, ...]
    verification_targets: tuple[str, ...]
    acceptance_artifacts: tuple[str, ...]
    rollback_paths: tuple[str, ...]
    external_dependencies: tuple[str, ...]
    non_claims: tuple[str, ...]
    operator_notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'featureId': self.feature_id,
            'capabilityIds': list(self.capability_ids),
            'title': self.title,
            'maturity': self.maturity,
            'entrySurfaces': list(self.entry_surfaces),
            'commands': list(self.commands),
            'authoritativeNodes': list(self.authoritative_nodes),
            'runtimeProducers': list(self.runtime_producers),
            'runtimeConsumers': list(self.runtime_consumers),
            'uiConsumers': list(self.ui_consumers),
            'configPaths': list(self.config_paths),
            'verificationTargets': list(self.verification_targets),
            'acceptanceArtifacts': list(self.acceptance_artifacts),
            'rollbackPaths': list(self.rollback_paths),
            'externalDependencies': list(self.external_dependencies),
            'nonClaims': list(self.non_claims),
            'operatorNotes': list(self.operator_notes),
        }



def _derive_feature_maturity(capability_ids: tuple[str, ...]) -> str:
    frontend_maturities = {get_capability_entry(capability_id).frontend_maturity for capability_id in capability_ids}
    if frontend_maturities == {'evidence_only'}:
        return 'evidence_only'
    if frontend_maturities == {'mainline_observability'}:
        return 'mainline_observability'
    if 'mainline_with_experimental_lane_isolation' in frontend_maturities:
        return 'mainline_with_experimental_lane_isolation'
    if 'mainline' in frontend_maturities and 'experimental_gated' in frontend_maturities:
        return 'mainline_with_experimental_lane_isolation'
    if frontend_maturities == {'experimental_gated'}:
        return 'experimental_gated'
    if 'mainline' in frontend_maturities:
        return 'mainline'
    return sorted(frontend_maturities)[0]



def _feature_entry(*, feature_id: str, title: str, entry_surfaces: tuple[str, ...], commands: tuple[str, ...], authoritative_nodes: tuple[str, ...], runtime_producers: tuple[str, ...], runtime_consumers: tuple[str, ...], ui_consumers: tuple[str, ...], config_paths: tuple[str, ...], verification_targets: tuple[str, ...], acceptance_artifacts: tuple[str, ...], rollback_paths: tuple[str, ...], external_dependencies: tuple[str, ...], non_claims: tuple[str, ...], operator_notes: tuple[str, ...]) -> FeatureAdmissionEntry:
    capability_ids = _FEATURE_TO_CAPABILITIES[feature_id]
    return FeatureAdmissionEntry(feature_id=feature_id, capability_ids=capability_ids, title=title, maturity=_derive_feature_maturity(capability_ids), entry_surfaces=entry_surfaces, commands=commands, authoritative_nodes=authoritative_nodes, runtime_producers=runtime_producers, runtime_consumers=runtime_consumers, ui_consumers=ui_consumers, config_paths=config_paths, verification_targets=verification_targets, acceptance_artifacts=acceptance_artifacts, rollback_paths=rollback_paths, external_dependencies=external_dependencies, non_claims=non_claims, operator_notes=operator_notes)


_FEATURE_ADMISSION_REGISTRY: dict[str, FeatureAdmissionEntry] = {
    'operator.mode_switch': _feature_entry(feature_id='operator.mode_switch', title='模式切换', entry_surfaces=('frontend_api_facade',), commands=('set_mode',), authoritative_nodes=('robot_decision',), runtime_producers=('robot_api_server', 'robot_web_bridge', '/robot/set_mode'), runtime_consumers=('robot_decision', 'robot_control'), ui_consumers=('ModePanel', 'TeleopPanel'), config_paths=('ros2_ws/src/robot_bringup/config/launch_profiles.yaml', 'robot_frontend/.env.example'), verification_targets=('test_governance_registry.py', 'test_frontend_authoritative_write_path.py', 'scripts/check_contract_consistency.py'), acceptance_artifacts=('host_harness_smoke',), rollback_paths=('set_mode:IDLE', 'backend-rollback surface'), external_dependencies=(), non_claims=('does_not_claim_board_side_mode_execution_evidence',), operator_notes=('9100 API facade 是唯一权威写入口。',)),
    'operator.teleop_control': _feature_entry(feature_id='operator.teleop_control', title='手动遥控', entry_surfaces=('frontend_api_facade',), commands=('teleop_cmd', 'stop_now'), authoritative_nodes=('robot_control',), runtime_producers=('robot_api_server', 'robot_web_bridge', '/robot/manual/cmd_vel'), runtime_consumers=('robot_control', 'robot_bridge'), ui_consumers=('TeleopPanel',), config_paths=('ros2_ws/src/robot_bringup/config/launch_profiles.yaml', 'docs/protocols/bridge-contract.md'), verification_targets=('test_governance_registry.py', 'test_frontend_authoritative_write_path.py', 'scripts/check_feature_admission.py'), acceptance_artifacts=('host_harness_smoke', 'command_audit_report', 'target_environment_acceptance'), rollback_paths=('stop_now', 'disable frontend operator session'), external_dependencies=('board_boundary_contract_or_verified_board_runtime',), non_claims=('does_not_claim_real_board_motion_acceptance_without_target_environment_acceptance',), operator_notes=('9001 observer 面必须拒绝写命令。',)),
    'operator.safety_recovery': _feature_entry(feature_id='operator.safety_recovery', title='急停与恢复', entry_surfaces=('frontend_api_facade',), commands=('estop', 'resume_from_safe_stop', 'reset_fault'), authoritative_nodes=('robot_control', 'robot_decision'), runtime_producers=('robot_api_server', 'robot_web_bridge', '/robot/set_mode', '/robot/reset_fault'), runtime_consumers=('robot_control', 'robot_decision'), ui_consumers=('FaultPanel',), config_paths=('docs/state-machine.md', 'docs/protocols/bridge-contract.md'), verification_targets=('test_governance_registry.py', 'scripts/check_contract_consistency.py', 'scripts/check_feature_admission.py'), acceptance_artifacts=('host_harness_smoke', 'command_audit_report', 'target_environment_acceptance'), rollback_paths=('estop latch remains available', 'backend-rollback surface'), external_dependencies=('board_boundary_contract_or_verified_board_runtime',), non_claims=('does_not_claim_hardware_line_level_estop_latency_inside_this_repo',), operator_notes=('安全命令允许 soft-warn 旁路，但最终裁决以后端 ACK 为准。',)),
    'operator.patrol_execution': _feature_entry(feature_id='operator.patrol_execution', title='巡检执行', entry_surfaces=('frontend_api_facade',), commands=('start_patrol', 'pause_patrol', 'stop_patrol'), authoritative_nodes=('robot_decision', 'robot_navigation'), runtime_producers=('robot_api_server', 'robot_web_bridge', 'robot_decision', 'robot_navigation'), runtime_consumers=('robot_navigation', 'robot_web_bridge', 'robot_bridge'), ui_consumers=('PatrolPanel',), config_paths=('ros2_ws/src/robot_bringup/config/navigation.yaml', 'ros2_ws/src/robot_navigation/robot_navigation/provider_contract.py'), verification_targets=('test_governance_registry.py', 'scripts/check_feature_admission.py', 'test_reporting_scripts.py'), acceptance_artifacts=('simulation_smoke', 'host_harness_smoke', 'runtime_signal_matrix_report', 'target_environment_acceptance', 'operator_docs_review', 'external_backend_smoke'), rollback_paths=('switch provider to simple_nav_provider', 'stop_patrol', 'backend-rollback surface'), external_dependencies=('board_boundary_contract_or_verified_board_runtime',), non_claims=('does_not_claim_external_nav2_stack_presence_when_adapter_runs_in_local_mode',), operator_notes=('simple_nav_provider 仍是默认主线；nav2_provider 当前是 governed local adapter runtime，默认隐藏并要求独立验收。',)),
    'operator.runtime_param_commit': _feature_entry(feature_id='operator.runtime_param_commit', title='运行参数提交', entry_surfaces=('frontend_api_facade',), commands=('apply_param_draft', 'apply_param_profile'), authoritative_nodes=('robot_control', 'robot_decision', 'robot_monitor'), runtime_producers=('robot_api_server', 'robot_web_bridge', 'runtime_param_coordinator'), runtime_consumers=('robot_control', 'robot_decision', 'robot_monitor'), ui_consumers=('ParamPanel',), config_paths=('ros2_ws/src/robot_bringup/config/*.yaml', 'ros2_ws/src/robot_contracts/robot_contracts/runtime_parameters.py'), verification_targets=('scripts/validate_configs.py', 'scripts/check_feature_admission.py', 'test_governance_registry.py'), acceptance_artifacts=('host_harness_smoke', 'parameter_schema_report'), rollback_paths=('apply_param_profile:last_known_good',), external_dependencies=(), non_claims=('does_not_claim_frontend_local_parameters_are_backend_authoritative',), operator_notes=('提交命令被接收不等于参数已稳定生效，必须看 lifecycleStatus 终态。',)),
    'operator.voice_fixed_text': _feature_entry(feature_id='operator.voice_fixed_text', title='固定播报', entry_surfaces=('frontend_api_facade',), commands=('speak_fixed_text',), authoritative_nodes=('robot_voice',), runtime_producers=('robot_api_server', 'robot_web_bridge', '/robot/speak_req'), runtime_consumers=('robot_voice', '/robot/speak_tx'), ui_consumers=('VoicePanel',), config_paths=('docs/protocols/bridge-contract.md',), verification_targets=('scripts/check_feature_admission.py', 'test_governance_registry.py'), acceptance_artifacts=('host_harness_smoke', 'command_audit_report', 'target_environment_acceptance'), rollback_paths=('disable voice ingress route',), external_dependencies=('external_esp32_board_runtime',), non_claims=('does_not_claim_external_amplifier_output_evidence_inside_this_repo',), operator_notes=('播报命令在 Ubuntu 侧闭环，最终外设播出证据需看目标环境验收。',)),
    'operator.snapshot_capture': _feature_entry(feature_id='operator.snapshot_capture', title='快照保存', entry_surfaces=('frontend_api_facade',), commands=('save_snapshot',), authoritative_nodes=('robot_vision',), runtime_producers=('robot_api_server', 'robot_web_bridge', '/robot/actions/save_snapshot'), runtime_consumers=('robot_vision',), ui_consumers=('VisionPanel', 'FaultPanel'), config_paths=('docs/protocols/bridge-contract.md',), verification_targets=('scripts/check_feature_admission.py', 'test_governance_registry.py'), acceptance_artifacts=('host_harness_smoke',), rollback_paths=('fallback to service /robot/save_snapshot when action unavailable',), external_dependencies=(), non_claims=('does_not_claim_camera_target_environment_stability_from_repo_only',), operator_notes=('动作优先，服务 fallback 仅作为协议兼容路径。',)),
    'observability.runtime_reports': _feature_entry(feature_id='observability.runtime_reports', title='运行观测与报告', entry_surfaces=('frontend_api_facade', 'bridge_observer_surface'), commands=(), authoritative_nodes=('robot_monitor',), runtime_producers=('robot_monitor', 'scripts/render_*_report.py'), runtime_consumers=('robot_web_bridge', 'startup_barrier'), ui_consumers=('ReportSummaryPanel',), config_paths=('docs/governance/capability-ownership.md', 'ros2_ws/src/robot_contracts/robot_contracts/signal_ownership.py'), verification_targets=('scripts/check_evidence_layering.py', 'test_reporting_scripts.py', 'test_governance_registry.py'), acceptance_artifacts=('release_quality_manifest', 'runtime_signal_matrix_report'), rollback_paths=('disable observer-only report surfacing',), external_dependencies=(), non_claims=('human_summary_reports_must_not_be_promoted_to_machine_gate_without_registry_update',), operator_notes=('除 runtime_supervision 外，报告默认是 human summary，不得越权充当机器验收事实。',)),
    'observability.system_replay_evidence': _feature_entry(feature_id='observability.system_replay_evidence', title='系统级回放证据', entry_surfaces=('release_reports',), commands=(), authoritative_nodes=('rosbag2_or_mcap_capture',), runtime_producers=('robot_monitor', 'build_system_replay_bundle.py', 'render_system_replay_report.py'), runtime_consumers=('release_quality_manifest', 'acceptance_review'), ui_consumers=('ReplayPanel',), config_paths=('docs/governance/replay-evidence.md', 'ros2_ws/src/robot_bringup/config/monitor.yaml'), verification_targets=('test_reporting_scripts.py', 'scripts/check_feature_admission.py'), acceptance_artifacts=('system_replay_bundle',), rollback_paths=('retain_frontend_local_replay_without_claiming_system_evidence',), external_dependencies=('rosbag2', 'mcap'), non_claims=('frontend_json_demo_replay_is_not_system_acceptance_evidence',), operator_notes=('系统级 replay 与前端本地 demo replay 必须分层。',)),
}

DEFAULT_FRONTEND_COMPONENTS_ROOT = Path(__file__).resolve().parents[4] / 'robot_frontend' / 'src' / 'components'
_FEATURE_PILLS_PATTERN = re.compile(r"FeatureMaturityPills\s+featureIds=\{\[([^\]]*)\]\}", re.DOTALL)
_FEATURE_ID_PATTERN = re.compile(r"'([^']+)'")


def frontend_feature_ui_bindings(components_root: Path | None = None) -> dict[str, tuple[str, ...]]:
    root = components_root or DEFAULT_FRONTEND_COMPONENTS_ROOT
    if not root.is_dir():
        return {}
    bindings: dict[str, set[str]] = {}
    for component_path in sorted(root.glob('*.tsx')):
        component_name = component_path.stem
        source = component_path.read_text(encoding='utf-8')
        for feature_group in _FEATURE_PILLS_PATTERN.findall(source):
            for feature_id in _FEATURE_ID_PATTERN.findall(feature_group):
                bindings.setdefault(feature_id, set()).add(component_name)
    return {feature_id: tuple(sorted(component_names)) for feature_id, component_names in sorted(bindings.items())}


def validate_feature_admission_ui_consumers(components_root: Path | None = None) -> list[str]:
    root = components_root or DEFAULT_FRONTEND_COMPONENTS_ROOT
    bindings = frontend_feature_ui_bindings(root)
    if root.is_dir() and not bindings:
        return ['frontend_feature_ui_bindings_empty']
    errors: list[str] = []
    for feature_id, entry in feature_admission_payload().items():
        declared = tuple(sorted(str(item) for item in entry.get('uiConsumers', [])))
        actual = bindings.get(feature_id, ())
        if declared != actual:
            errors.append(f'{feature_id}:ui_consumers_mismatch:declared={list(declared)}:actual={list(actual)}')
    for feature_id in sorted(bindings):
        if feature_id not in _FEATURE_ADMISSION_REGISTRY:
            errors.append(f'{feature_id}:frontend_binding_without_registry_entry')
    return errors


def feature_admission_payload() -> dict[str, dict[str, Any]]:
    return {key: entry.to_dict() for key, entry in _FEATURE_ADMISSION_REGISTRY.items()}


def validate_feature_admission_registry(components_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    command_to_feature: dict[str, str] = {}
    payload = feature_admission_payload()
    for feature_id, entry in payload.items():
        capability_ids = tuple(str(item) for item in entry.get('capabilityIds', []))
        if not capability_ids:
            errors.append(f'{feature_id}:missing_capability_ids')
        elif entry.get('maturity') != _derive_feature_maturity(capability_ids):
            errors.append(f'{feature_id}:maturity_not_derived_from_capability_registry')
        for capability_id in capability_ids:
            try:
                get_capability_entry(capability_id)
            except ValueError:
                errors.append(f'{feature_id}:unknown_capability:{capability_id}')
        for required_key in ('entrySurfaces', 'authoritativeNodes', 'runtimeProducers', 'runtimeConsumers', 'configPaths', 'verificationTargets', 'acceptanceArtifacts', 'rollbackPaths'):
            value = list(entry.get(required_key, []))
            if not value:
                errors.append(f'{feature_id}:missing_{required_key}')
        known_surfaces = surface_registry_payload()
        for surface_id in [str(item) for item in entry.get('entrySurfaces', [])]:
            if surface_id not in known_surfaces:
                errors.append(f'{feature_id}:unknown_entry_surface:{surface_id}')
        commands = [str(item) for item in entry.get('commands', [])]
        for command in commands:
            if command in command_to_feature:
                errors.append(f'{feature_id}:duplicate_command_owner:{command}')
            command_to_feature[command] = feature_id
        external_dependencies = [str(item) for item in entry.get('externalDependencies', [])]
        acceptance = [str(item) for item in entry.get('acceptanceArtifacts', [])]
        if any(item.startswith('external_') for item in external_dependencies) and 'target_environment_acceptance' not in acceptance:
            errors.append(f'{feature_id}:missing_target_environment_acceptance')
    for command in COMMAND_TYPES:
        if command not in command_to_feature:
            errors.append(f'command_not_admitted:{command}')
    errors.extend(validate_feature_admission_ui_consumers(components_root))
    return errors
