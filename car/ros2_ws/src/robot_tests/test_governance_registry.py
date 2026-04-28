from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from robot_contracts.capability_registry import capability_registry_payload
from robot_contracts.feature_admission import feature_admission_payload, frontend_feature_ui_bindings, validate_feature_admission_registry
from robot_contracts.lane_registry import lane_registry_payload
from robot_contracts.signal_ownership import governance_signal_registry_payload, validate_signal_registry
from robot_contracts.command_route_registry import command_route_registry_payload, validate_command_route_registry
from robot_contracts.surface_registry import surface_registry_payload, validate_surface_registry
from robot_contracts.runtime_orchestration_registry import runtime_orchestration_registry_payload, validate_runtime_orchestration_registry
from robot_contracts.navigation_adapter_boundary_registry import navigation_adapter_boundary_registry_payload, validate_navigation_adapter_boundary_registry
from robot_contracts.release_gate_registry import release_gate_registry_payload, validate_release_gate_registry

ROOT = Path(__file__).resolve().parents[3]


def test_signal_registry_validation_has_no_errors() -> None:
    assert validate_signal_registry() == []
    payload = governance_signal_registry_payload()
    assert payload['validationErrors'] == []
    assert payload['runtimeParameters']['maxLinearSpeed']['ackOwners'] == ['robot_control', 'robot_decision']
    assert payload['reports']['runtime_supervision']['evidenceLayer'] == 'machine_gate'
    assert payload['reports']['monitor_summary']['evidenceLayer'] == 'human_summary'


def test_lane_registry_contains_lifecycle_exposure_and_capability_binding_fields() -> None:
    payload = lane_registry_payload(include_experimental=True)
    assert payload['navigation.nav2_provider']['lifecycleStage'] == 'experimental'
    assert payload['navigation.nav2_provider']['defaultSurfaceExposure'] == 'hidden_by_default'
    assert payload['navigation.nav2_provider']['capabilityId'] == 'navigation.nav2_provider'
    assert 'external_backend_smoke' in payload['navigation.nav2_provider']['evidenceRequired']
    assert payload['bridge_runtime.legacy_monolith']['activationDecision'] == 'rollback_only'
    assert payload['bridge_runtime.legacy_monolith']['lifecycleStage'] == 'rollback_only'


def test_feature_admission_registry_covers_all_operator_commands_and_capability_bindings() -> None:
    assert validate_feature_admission_registry() == []
    payload = feature_admission_payload()
    capabilities = capability_registry_payload()
    commands = {command for entry in payload.values() for command in entry['commands']}
    for required in ('set_mode', 'teleop_cmd', 'start_patrol', 'apply_param_draft', 'save_snapshot'):
        assert required in commands
    assert 'observability.system_replay_evidence' in payload
    assert 'target_environment_acceptance' in payload['operator.voice_fixed_text']['acceptanceArtifacts']
    assert payload['operator.patrol_execution']['capabilityIds'] == ['operator.patrol_execution', 'navigation.simple_nav_provider', 'navigation.nav2_provider']
    assert payload['operator.teleop_control']['externalDependencies'] == ['board_boundary_contract_or_verified_board_runtime']
    assert payload['operator.safety_recovery']['externalDependencies'] == ['board_boundary_contract_or_verified_board_runtime']
    assert payload['operator.patrol_execution']['externalDependencies'] == ['board_boundary_contract_or_verified_board_runtime']
    for entry in payload.values():
        assert entry['capabilityIds']
        for capability_id in entry['capabilityIds']:
            assert capability_id in capabilities




def test_command_route_surface_and_runtime_governance_registries_are_consistent() -> None:
    assert validate_command_route_registry() == []
    assert validate_surface_registry() == []
    assert validate_runtime_orchestration_registry() == []
    command_routes = command_route_registry_payload()
    surface_registry = surface_registry_payload()
    runtime_registry = runtime_orchestration_registry_payload()
    assert command_routes['teleop_cmd']['timeoutBudgetMs'] == 250
    assert 'latest_only_supersession' in command_routes['teleop_cmd']['fallbackPaths']
    assert command_routes['save_snapshot']['fallbackPaths'] == ['action:/robot/actions/save_snapshot', 'service:/robot/save_snapshot']
    assert surface_registry['frontend_api_facade']['writeEnabled'] is True
    assert surface_registry['bridge_observer_surface']['writeEnabled'] is False
    assert 'command_control' in surface_registry['frontend_api_facade']['surfaceLayers']
    assert 'observability_report' in surface_registry['bridge_observer_surface']['surfaceLayers']
    assert runtime_registry['recovery_plan']['reportKey'] == 'runtimeSupervision'
    assert 'recoveryPlan.strategy' in runtime_registry['recovery_plan']['operatorVisibleFields']


def test_navigation_adapter_boundary_and_release_gate_registries_are_consistent() -> None:
    assert validate_navigation_adapter_boundary_registry() == []
    assert validate_release_gate_registry() == []
    adapter_registry = navigation_adapter_boundary_registry_payload()
    release_gates = release_gate_registry_payload()
    assert adapter_registry['nav2_provider']['adapterRuntime'] is True
    assert adapter_registry['nav2_provider']['defaultMainline'] is False
    assert 'external_backend_smoke' in adapter_registry['nav2_provider']['promotionChecklist']
    assert adapter_registry['nav2_provider']['rollbackBaseline'] == 'simple_nav_provider'
    assert release_gates['command_route_governance']['blockingByDefault'] is True
    assert 'scripts/check_command_route_registry.py' in release_gates['command_route_governance']['scriptPaths']
    assert 'scripts/check_report_kind_enum_closure.py' in release_gates['contract_consistency']['scriptPaths']


def test_generate_governance_artifacts_emits_frontend_contract_files() -> None:
    script = ROOT / 'scripts' / 'generate_governance_artifacts.py'
    subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=True)
    json_path = ROOT / 'robot_frontend' / 'src' / 'generated' / 'governanceContract.json'
    ts_path = ROOT / 'robot_frontend' / 'src' / 'generated' / 'governanceContract.ts'
    payload = json.loads(json_path.read_text(encoding='utf-8'))
    assert json_path.is_file()
    assert ts_path.is_file()
    assert payload['laneRegistry']['navigation.nav2_provider']['lifecycleStage'] == 'experimental'
    assert payload['laneRegistry']['navigation.nav2_provider']['capabilityId'] == 'navigation.nav2_provider'
    assert 'external_backend_smoke' in payload['laneRegistry']['navigation.nav2_provider']['evidenceRequired']
    assert payload['signalRegistry']['reports']['runtime_supervision']['evidenceLayer'] == 'machine_gate'
    assert 'featureAdmissionRegistry' in payload
    assert 'operator.teleop_control' in payload['featureAdmissionRegistry']
    assert payload['featureAdmissionRegistry']['operator.teleop_control']['capabilityIds'] == ['operator.teleop_control']
    assert payload['featureAdmissionRegistry']['operator.teleop_control']['externalDependencies'] == ['board_boundary_contract_or_verified_board_runtime']
    assert payload['capabilityRegistry']['observability.standard_readonly_bridge']['implementationStatus'] == 'repo_audited_readonly_proxy_runtime'
    assert payload['capabilityRegistry']['orchestration.fleet_adapter_boundary']['implementationStatus'] == 'single_robot_runtime_boundary_contract'
    assert payload['commandRouteRegistry']['teleop_cmd']['timeoutBudgetMs'] == 250
    assert payload['surfaceRegistry']['bridge_observer_surface']['writeEnabled'] is False
    assert payload['runtimeOrchestrationRegistry']['startup_barrier']['requiredForMainline'] is True
    assert payload['navigationAdapterBoundaryRegistry']['nav2_provider']['rollbackBaseline'] == 'simple_nav_provider'
    assert 'command_route_governance' in payload['releaseGateRegistry']
    assert 'mock' in payload['profileRegistry']


def test_feature_admission_ui_consumers_match_frontend_components() -> None:
    bindings = frontend_feature_ui_bindings()
    payload = feature_admission_payload()
    assert bindings['operator.mode_switch'] == ('ModePanel', 'TeleopPanel')
    assert bindings['operator.snapshot_capture'] == ('FaultPanel', 'VisionPanel')
    assert bindings['observability.system_replay_evidence'] == ('ReplayPanel',)
    for feature_id, entry in payload.items():
        assert tuple(sorted(entry['uiConsumers'])) == bindings.get(feature_id, ())


def test_feature_admission_ui_consumer_validation_fails_when_no_frontend_bindings_exist(tmp_path: Path) -> None:
    components_root = tmp_path / 'components'
    components_root.mkdir()
    (components_root / 'Placeholder.tsx').write_text("export function Placeholder() { return null; }\n", encoding='utf-8')
    errors = validate_feature_admission_registry(components_root=components_root)
    assert 'frontend_feature_ui_bindings_empty' in errors
