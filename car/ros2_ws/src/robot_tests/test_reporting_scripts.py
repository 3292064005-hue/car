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
    assert 'SAFE_STOP' in payload['modes']


def test_parameter_schema_report_script_runs() -> None:
    payload = _run('render_parameter_schema_report.py')
    assert payload['counts']['patrol_steps'] >= 1
    assert 'dev' in payload['validated']['launch_profiles']


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
    assert payload['report_scope'] == 'audit_inventory_only'
    assert payload['runtime_consumer_closure_completed'] is False
    assert payload['observability_consumer_governance_completed'] is True
    assert '/robot/decision/summary' in payload['mainline_topics']
    assert '/robot/web_bridge/ready' in payload['mainline_topics']
    assert '/robot/monitor/diagnostics_json' in payload['observability_only_topics']


def test_bridge_runtime_topology_report_script_runs() -> None:
    payload = _run('render_bridge_runtime_topology_report.py')
    assert payload['report_scope'] == 'policy_artifact_only'
    assert payload['mainline_runtime'] == 'split_runtime'
    assert payload['runtime_launch_surface_changed'] is True
    assert payload['launchSurface']['operatorBarrierEnabled'] is True
    assert payload['policy']['legacy_runtime_accepts_new_features'] is False


def test_runtime_signal_matrix_report_honors_minimal_profile() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPTS / 'render_runtime_signal_matrix_report.py'), '--profile', 'minimal'], cwd=str(ROOT), text=True, capture_output=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload['profile'] == 'minimal'
    assert '/robot/runtime/supervision' not in payload['mainline_topics']
