from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / 'ubuntu_side' / 'scripts'

def _run(script: str) -> dict[str, object]:
    proc = subprocess.run([sys.executable, str(SCRIPTS / script)], text=True, capture_output=True, check=True)
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
