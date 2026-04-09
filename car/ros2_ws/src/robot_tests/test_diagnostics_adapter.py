from robot_monitor.diagnostics_adapter import diagnostic_transport_type, make_diagnostic_status
from robot_monitor.status_aggregator import StatusSnapshot


def test_make_diagnostic_status_fallback_or_message():
    snapshot = StatusSnapshot(mode='IDLE', wifi_ok=True, camera_ok=True, audio_ok=True, uart_ok=True, bridge_ok=True)
    payload = make_diagnostic_status(snapshot)
    if diagnostic_transport_type() == 'json_string':
        assert 'inspection_robot/system' in payload
        assert 'IDLE' in payload
    else:
        assert payload.name == 'inspection_robot/system'
        assert payload.message == 'all_core_modules_ok'
