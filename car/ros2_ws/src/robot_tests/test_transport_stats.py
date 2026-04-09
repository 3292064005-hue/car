from robot_monitor.status_aggregator import StatusSnapshot, derive_health, derive_readiness


def test_stale_bridge_degrades_health_and_readiness():
    snap = StatusSnapshot(mode='IDLE', wifi_ok=True, camera_ok=True, audio_ok=True, uart_ok=True, bridge_ok=True, stale_bridge=True)
    readiness, reason = derive_readiness(snap)
    assert readiness == 'degraded'
    assert reason == 'bridge_stale'
    assert derive_health(snap) == 'degraded'
