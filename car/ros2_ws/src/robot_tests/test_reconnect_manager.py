from robot_bridge.reconnect_manager import ReconnectManager


def test_reconnect_manager_backs_off_and_recovers():
    mgr = ReconnectManager(0.1, max_period_sec=1.0, multiplier=2.0)
    mgr.mark_result(False)
    assert mgr.current_period_sec == 0.2
    mgr.mark_result(False)
    assert mgr.current_period_sec == 0.4
    mgr.mark_result(True)
    assert mgr.current_period_sec == 0.1
    summary = mgr.summary()
    assert summary['reconnect_state'] == 'connected'
    assert summary['reconnect_backoff_sec'] == 0.1
