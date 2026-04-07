from robot_bridge.health_monitor import LinkHealth


def test_link_health_summary_exposes_state_and_rates() -> None:
    health = LinkHealth(connected=True)
    health.last_connected_at = health.last_tx_at = health.last_rx_at = 1.0
    health.rx_messages = 4
    health.tx_messages = 2
    summary = health.summary()
    assert summary['state'] in {'connected', 'stale'}
    assert 'inbound_rate_hz' in summary
    assert 'outbound_rate_hz' in summary


def test_link_health_degraded_when_protocol_errors_present() -> None:
    health = LinkHealth(connected=True, protocol_errors=1)
    health.last_connected_at = health.last_tx_at = health.last_rx_at = 1.0
    summary = health.summary()
    assert summary['state'] == 'degraded'
    assert summary['transport_degraded'] is True
