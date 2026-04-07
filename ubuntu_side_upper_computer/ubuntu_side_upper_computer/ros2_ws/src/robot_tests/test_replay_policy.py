from robot_bridge.protocol_policy import ReplayOptions, filter_replay_payloads, should_replay_payload


def test_should_replay_payload_respects_options():
    payload = {'type': 'fault'}
    assert should_replay_payload(payload)
    assert not should_replay_payload(payload, options=ReplayOptions(include_faults=False))


def test_filter_replay_payloads_filters_non_replayables():
    payloads = [
        {'type': 'pong'},
        {'type': 'voice_cmd'},
        {'type': 'system_status'},
    ]
    filtered = filter_replay_payloads(payloads, options=ReplayOptions(include_voice=False))
    assert filtered == [{'type': 'system_status'}]
