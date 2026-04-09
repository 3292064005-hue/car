from robot_web_bridge.envelope import EnvelopeFactory, build_connection_payload
from robot_web_bridge.state_model import WebBridgeState


def test_envelope_factory_ack_supports_detail():
    env = EnvelopeFactory().ack('cmd-1', 'ack', 'done', detail='ok', lifecycle_status='completed')
    assert env['type'] == 'command_ack'
    assert env['payload']['detail'] == 'ok'
    assert env['payload']['lifecycleStatus'] == 'completed'


def test_connection_payload_uses_transport_stats():
    state = WebBridgeState(
        bridge_summary={'connected': True, 'last_rtt_ms': 12.3, 'heartbeat_age_sec': 0.2, 'reconnect_count': 2},
        transport_stats={'stale_link': True, 'inbound_rate_hz': 8.0, 'outbound_rate_hz': 4.0},
        system_status={'uart_ok': True, 'camera_ok': False, 'audio_ok': True, 'low_power_warn': True},
    )
    payload = build_connection_payload(state)
    assert payload['bridgeConnected'] is True
    assert payload['staleMotion'] is True
    assert payload['staleVision'] is True
    assert payload['reconnectAttempts'] == 2
    assert payload['runtimeHealthState'] == 'degraded'
    assert 'vision_stale_or_unavailable' in payload['runtimeHealthReasons']
    assert payload['operatorReady'] is False
    assert payload['operatorReadyTopic'] is None
