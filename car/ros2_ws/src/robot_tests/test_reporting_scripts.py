from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'scripts'


def _run(script: str) -> dict[str, object]:
    proc = subprocess.run([sys.executable, str(SCRIPTS / script)], cwd=str(ROOT), text=True, capture_output=True, check=True)
    return json.loads(proc.stdout)


def test_state_transition_report_script_runs() -> None:
    payload = _run('render_state_transition_report.py')
    assert 'transition_rows' in payload
    assert payload['authority'] == 'robot_utils.mode_catalog'
    assert payload['allowed_matrix']['FAULT'] == ['IDLE']
    assert 'SAFE_STOP' in payload['modes']


def test_parameter_schema_report_script_runs() -> None:
    payload = _run('render_parameter_schema_report.py')
    assert payload['retiredSchemas']['patrol_step'] == 'removed_from_runtime_surface'
    assert 'dev' in payload['validated']['launch_profiles']
    assert payload['counts']['launch_profiles'] >= 1


def test_control_summary_report_script_runs() -> None:
    payload = _run('render_control_summary_report.py')
    assert payload['limits']['max_linear'] > 0
    assert 'FAULT/SAFE_STOP' in payload['source_priority']


def test_voice_reject_report_script_runs() -> None:
    payload = _run('render_voice_reject_report.py')
    assert 'forward' in payload['cooldown_sec']
    assert payload['allowed_matrix']['forward']['MANUAL'] is True
    assert payload['allowed_matrix']['forward']['IDLE'] is False
    assert payload['allowed_matrix']['resume_from_safe_stop']['SAFE_STOP'] is True
    assert payload['allowed_matrix']['resume_from_safe_stop']['IDLE'] is False
    assert payload['allowed_matrix']['start_patrol']['IDLE'] is True
    assert payload['allowed_matrix']['start_patrol']['MANUAL'] is False


def test_vision_stability_report_script_runs() -> None:
    payload = _run('render_vision_stability_report.py')
    assert payload['stable_detection_hits'] >= 1
    assert len(payload['tracker_simulation']) >= 3


def test_command_audit_report_script_runs() -> None:
    payload = _run('render_command_audit_report.py')
    assert 'teleop_cmd' in payload['permission_matrix']
    assert 'ack' in payload['ack_statuses']


def test_fault_dictionary_report_script_runs() -> None:
    payload = _run('render_fault_dictionary_report.py')
    assert payload['count'] >= 5
    assert 'ESTOP' in payload['latched_codes']


def test_command_permission_matrix_report_script_runs() -> None:
    payload = _run('render_command_permission_matrix_report.py')
    assert 'teleop_cmd' in payload['manual_only_commands']
    assert 'resume_from_safe_stop' in payload['safe_stop_only_commands']
    assert 'start_patrol' in payload['idle_only_commands']


def test_transport_summary_report_script_runs() -> None:
    payload = _run('render_transport_summary_report.py')
    assert 'transport_summary_keys' in payload
    assert payload['sample_connected_summary']['state'] in {'connected', 'degraded', 'stale', 'disconnected'}


def test_monitor_summary_report_script_runs() -> None:
    payload = _run('render_monitor_summary_report.py')
    assert payload['topic'] == '/robot/monitor/summary'
    assert payload['classification'] == 'monitor_observability_governed'
    assert 'render_monitor_summary_report' in payload['evidence_consumers']


def test_monitor_diagnostics_report_script_runs() -> None:
    payload = _run('render_monitor_diagnostics_report.py')
    assert payload['topic'] == '/robot/monitor/diagnostics_json'
    assert payload['classification'] == 'diagnostics_export_governed'
    assert payload['componentStatusCount'] >= 1
    assert 'render_monitor_diagnostics_report' in payload['evidence_consumers']


def test_runtime_signal_matrix_report_script_runs() -> None:
    payload = _run('render_runtime_signal_matrix_report.py')
    assert payload['report_scope'] == 'profile_aware_runtime_contract'
    assert payload['closureTracks']['declared']['complete'] is True
    assert payload['closureTracks']['observed']['complete'] is True
    assert payload['runtime_consumer_closure_completed'] is True
    assert payload['mainline_runtime_gaps'] == []
    assert payload['capabilitySnapshot']['web_bridge'] is True
    assert payload['observability_consumer_governance_completed'] is True
    assert '/robot/decision/summary' in payload['mainline_topics']
    assert '/robot/web_bridge/ready' in payload['mainline_topics']
    assert '/robot/monitor/diagnostics_json' in payload['observability_only_topics']
    assert payload['topic_pruning_applied'] is True
    assert payload['observability_surface_split_completed'] is True
    assert payload['projection_surface_runtime_split_completed'] is True
    row_by_topic = {row['topic']: row for row in payload['signalRows']}
    assert row_by_topic['/robot/monitor/diagnostics_json']['surface_owner'] == 'observability_surface'
    assert row_by_topic['/robot/decision/summary']['surface_owner'] == 'projection_surface'


def test_bridge_runtime_topology_report_script_runs() -> None:
    payload = _run('render_bridge_runtime_topology_report.py')
    assert payload['report_scope'] == 'policy_artifact_only'
    assert payload['closureTracks']['declared']['complete'] is True
    assert payload['closureTracks']['observed']['complete'] is False
    assert payload['mainline_runtime'] == 'split_runtime'
    assert payload['runtime_launch_surface_changed'] is True
    assert payload['launchSurface']['operatorBarrierEnabled'] is True
    assert payload['policy']['legacy_runtime_accepts_new_features'] is False
    assert payload['legacy_runtime_removed_from_launch'] is True


def test_runtime_signal_matrix_report_honors_minimal_profile() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPTS / 'render_runtime_signal_matrix_report.py'), '--profile', 'minimal'], cwd=str(ROOT), text=True, capture_output=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload['profile'] == 'minimal'
    assert '/robot/runtime/supervision' not in payload['mainline_topics']


def test_legacy_compatibility_report_script_runs() -> None:
    payload = _run('render_legacy_compatibility_report.py')
    assert payload['retirementStage'] == 'audit_enforced'
    assert payload['retirementMilestones'][1]['targetVersion'] == '4.1.0'
    assert payload['runtimeAudit']['motionInputAliasHits'] >= 0
    assert payload['canAdvanceMilestones']['remove_motion_input_tolerance'] in {True, False}


def test_generated_mode_transition_artifact_matches_backend_catalog() -> None:
    payload = json.loads((ROOT / 'robot_frontend' / 'src' / 'generated' / 'modeTransitions.json').read_text(encoding='utf-8'))
    assert payload['authority'] == 'backend_mode_catalog'
    assert payload['transitions']['IDLE'] == ['MANUAL', 'PATROL', 'SAFE_STOP', 'FAULT']
    assert payload['transitions']['FAULT'] == ['IDLE']


def test_repository_boundary_report_script_runs() -> None:
    payload = _run('render_repository_boundary_report.py')
    assert payload['repositoryRole'] == 'ubuntu_authoritative_runtime_plus_board_boundary_contract'
    assert payload['repositoryClaims']['boardRuntimeInRepo'] is True
    assert payload['authoritativeWriteEntry'] == 'robot_api_server:9100/ws'


def test_feature_admission_report_script_runs() -> None:
    payload = _run('render_feature_admission_report.py')
    assert payload['reportScope'] == 'feature_admission_governance'
    assert payload['status'] == 'ok'
    assert 'operator.mode_switch' in payload['features']


def test_capability_ownership_report_script_runs() -> None:
    payload = _run('render_capability_ownership_report.py')
    assert payload['reportScope'] == 'capability_ownership'
    assert payload['commandOwners']['teleop_cmd'] == 'operator.teleop_control'
    assert 'runtime_supervision' in payload['machineGateReports']


def test_lane_lifecycle_report_script_runs() -> None:
    payload = _run('render_lane_lifecycle_report.py')
    assert payload['reportScope'] == 'lane_lifecycle'
    assert 'navigation.nav2_provider' in payload['experimentalLanes']
    assert 'bridge_runtime.legacy_monolith' in payload['rollbackOnlyLanes']
    assert 'navigation.simple_nav_provider' in payload['defaultVisibleLanes']
    assert 'navigation.nav2_provider' in payload['hiddenByDefaultLanes']


def test_system_replay_report_script_runs() -> None:
    payload = _run('render_system_replay_report.py')
    assert payload['reportScope'] == 'system_replay_evidence'
    assert payload['frontendReplay']['countsAsSystemEvidence'] is False
    assert 'mcap' in payload['systemReplay']['supportedFormats']
    assert payload['systemReplay']['kind'] == 'system-replay-bundle'


def test_runtime_topology_manifest_script_runs() -> None:
    payload = _run('render_runtime_topology_manifest.py')
    assert payload['reportScope'] == 'runtime_topology_manifest'
    assert payload['surfaces']['frontend']['runtimeSurface']['websocketSurfaceKind'] == 'api_facade'
    assert payload['surfaces']['web_bridge']['runtimeSurface']['websocketSurfaceKind'] == 'bridge_observer'
    assert 'operator_phase' in payload['startupSequence']
    assert 'navigation.simple_nav_provider' in payload['defaultVisibleLanes']
    assert 'bridge_runtime.legacy_monolith' in payload['hiddenByDefaultLanes']


def test_build_system_replay_bundle_script_rejects_missing_required_session_metadata_file(tmp_path) -> None:
    output = tmp_path / 'bundle.json'
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / 'build_system_replay_bundle.py'),
            '--session-metadata',
            str(tmp_path / 'missing.json'),
            '--output',
            str(output),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert 'required JSON input not found' in (proc.stderr or proc.stdout)


def test_build_system_replay_bundle_script_writes_valid_bundle(tmp_path) -> None:
    session = tmp_path / 'session.json'
    history = tmp_path / 'history.json'
    session.write_text(json.dumps({
        'sessionId': 's1',
        'profileName': 'mock',
        'providerName': 'nav2_provider',
        'hardwareRole': 'ros_soft_driver',
        'evidenceClass': 'target_environment',
    }), encoding='utf-8')
    history.write_text(json.dumps({
        'latency': [],
        'battery': [],
        'leftWheel': [],
        'rightWheel': [],
        'frameDrops': [],
        'ackLatency': [],
    }), encoding='utf-8')
    output = tmp_path / 'bundle.json'
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / 'build_system_replay_bundle.py'),
            '--session-metadata',
            str(session),
            '--history',
            str(history),
            '--output',
            str(output),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['kind'] == 'system-replay-bundle'
    assert payload['history']['ackLatency'] == []
