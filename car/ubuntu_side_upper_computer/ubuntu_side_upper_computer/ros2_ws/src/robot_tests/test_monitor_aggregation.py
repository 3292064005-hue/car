from robot_monitor.dashboard_adapter import render_text
from robot_monitor.diagnostics_adapter import make_diagnostic_status
from robot_monitor.status_aggregator import StatusSnapshot, derive_health, derive_readiness


def test_dashboard_renders_readiness():
    snap = StatusSnapshot(mode='IDLE', readiness='ready', readiness_reason='all_core_modules_ok')
    text = render_text(snap)
    assert 'readiness=ready' in text
    assert 'reason=all_core_modules_ok' in text


def test_health_and_readiness_derivation():
    snap = StatusSnapshot(mode='IDLE', wifi_ok=True, camera_ok=True, audio_ok=True, uart_ok=True, bridge_ok=True)
    readiness, reason = derive_readiness(snap)
    assert readiness == 'ready'
    assert reason == 'all_core_modules_ok'
    assert derive_health(snap) == 'good'


def test_diagnostics_payload_contains_mode():
    snap = StatusSnapshot(mode='PATROL', wifi_ok=True, camera_ok=True, audio_ok=True, uart_ok=True, bridge_ok=True)
    payload = make_diagnostic_status(snap)
    if isinstance(payload, str):
        assert 'PATROL' in payload
    else:
        assert payload.name == 'inspection_robot/system'
