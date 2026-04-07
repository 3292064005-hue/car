from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / 'ubuntu_side' / 'tools'
SCRIPTS = ROOT / 'ubuntu_side' / 'scripts'

def test_fault_injector_and_replay_tools_exist() -> None:
    assert (TOOLS / 'tcp_fault_injector.py').exists()
    assert (TOOLS / 'tcp_replay_client.py').exists()
    assert (TOOLS / 'transport_capture.py').exists()

def test_reporting_scripts_exist() -> None:
    required = ['render_state_transition_report.py','render_parameter_schema_report.py','render_control_summary_report.py','render_vision_stability_report.py','render_voice_reject_report.py','render_command_audit_report.py','render_fault_dictionary_report.py','render_command_permission_matrix_report.py','render_transport_summary_report.py','archive_metrics.py', 'check_frontend_bundle_budget.py', 'check_web_bridge_payload_budget.py']
    for name in required:
        assert (SCRIPTS / name).exists(), name


def test_preflight_environment_script_reports_target_env() -> None:
    import json, subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[4]
    proc = subprocess.run([sys.executable, str(root / 'ubuntu_side' / 'scripts' / 'preflight_environment_check.py')], text=True, capture_output=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload['target_environment']['os'] == 'Ubuntu 22.04 LTS'
    assert 'python_3_10_plus' in payload['environment_constraints']
    assert payload['fault_dictionary_report_script_exists'] is True
    assert payload['command_permission_matrix_report_script_exists'] is True
    assert payload['transport_summary_report_script_exists'] is True
