from robot_web_bridge.envelope import build_connection_payload
from robot_web_bridge.state_model import WebBridgeState


def test_connection_payload_prefers_state_stale_flags_and_transport_state() -> None:
    state = WebBridgeState(
        bridge_summary={'connected': False, 'reconnect_count': 3, 'last_rtt_ms': 8.5, 'heartbeat_age_sec': 1.7},
        transport_stats={'state': 'reconnecting', 'transport_degraded': True, 'inbound_rate_hz': 5.0, 'outbound_rate_hz': 2.5},
        system_status={'uart_ok': True, 'camera_ok': True, 'audio_ok': False},
    )
    state.stale_flags.update({'bridge': True, 'transport': True, 'voice': True, 'vision': False, 'power': False, 'chassis': False})
    payload = build_connection_payload(state)
    assert payload['reconnecting'] is True
    assert payload['staleMotion'] is True
    assert payload['staleVoice'] is True
    assert payload['transportLabel'] == 'reconnecting'
