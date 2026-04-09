from __future__ import annotations

from robot_monitor.diagnostics_adapter import make_diagnostic_statuses, diagnostic_transport_type
from robot_monitor.status_aggregator import StatusSnapshot


def test_make_diagnostic_statuses_count() -> None:
    snapshot = StatusSnapshot(
        mode='PATROL', wifi_ok=True, camera_ok=True, audio_ok=True, uart_ok=True, bridge_ok=True,
        battery_voltage=11.3, control_source='patrol',
    )
    statuses = make_diagnostic_statuses(snapshot)
    assert len(statuses) >= 6


def test_diagnostic_transport_type_declared() -> None:
    assert diagnostic_transport_type() in {'diagnostic_array', 'json_string'}


def test_make_diagnostic_statuses_marks_stale_component() -> None:
    snapshot = StatusSnapshot(mode='PATROL', wifi_ok=True, camera_ok=True, audio_ok=True, uart_ok=True, bridge_ok=True, stale_bridge=True)
    statuses = make_diagnostic_statuses(snapshot)
    bridge = statuses[1]
    if diagnostic_transport_type() == 'json_string':
        assert '"level": 3' in bridge
    else:
        assert bridge.level == 3
