from robot_bridge.protocol_policy import classify_payload, should_replay_payload


def test_classify_payload_accepts_valid_status():
    decision = classify_payload({'type': 'system_status', 'wifi_ok': True, 'camera_ok': True, 'audio_ok': True, 'uart_ok': True, 'proto_ver': 1})
    assert decision.action == 'accept'


def test_classify_payload_warns_on_missing_field():
    decision = classify_payload({'type': 'system_status', 'wifi_ok': True, 'camera_ok': True})
    assert decision.action == 'warn'


def test_classify_payload_faults_on_version_mismatch():
    decision = classify_payload({'type': 'pong', 'seq': 1, 'proto_ver': 99})
    assert decision.action == 'fault'


def test_replay_filter_skips_pong():
    assert should_replay_payload({'type': 'pong', 'seq': 1}) is False
    assert should_replay_payload({'type': 'fault', 'code': 'X', 'level': 'warn'}) is True
