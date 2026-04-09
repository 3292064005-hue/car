from robot_bridge.health_monitor import LinkHealth


def test_link_health_tracks_queue_and_disconnect_reason():
    health = LinkHealth()
    health.mark_connected(True)
    health.update_queue(queue_depth=3, dropped_payloads=1)
    health.mark_tx('cmd_vel')
    health.mark_rx('pong')
    health.mark_disconnect('heartbeat_timeout')
    summary = health.summary()
    assert summary['queue_depth'] == 3
    assert summary['dropped_payloads'] == 1
    assert summary['last_disconnect_reason'] == 'heartbeat_timeout'
    assert summary['last_tx_type'] == 'cmd_vel'
    assert summary['last_rx_type'] == 'pong'
