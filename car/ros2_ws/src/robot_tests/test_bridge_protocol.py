from robot_bridge.command_payloads import build_cmd_vel_payload, motion_from_payload, normalize_motion_payload
from robot_bridge.json_codec import validate_payload


def test_validate_valid_voice_payload():
    ok, reason = validate_payload({'type': 'voice_cmd', 'cmd': 'start_patrol', 'proto_ver': 1})
    assert ok
    assert reason == 'ok'


def test_validate_missing_field():
    ok, reason = validate_payload({'type': 'fault', 'proto_ver': 1, 'code': 'LOW_BAT'})
    assert not ok
    assert 'missing field' in reason


def test_cmd_vel_contract_emits_canonical_fields_and_tolerates_legacy_input():
    payload = build_cmd_vel_payload(seq=3, vx=0.2, wz=-0.1, mode='MANUAL', timestamp=1.23)
    ok, reason = validate_payload(payload)
    assert ok, reason
    assert set(payload) >= {'vx', 'wz'}
    assert 'linear' not in payload
    assert 'angular' not in payload
    assert motion_from_payload({'type': 'cmd_vel', 'vx': 0.2, 'wz': -0.1}) == (0.2, -0.1)
    assert motion_from_payload({'type': 'cmd_vel', 'linear': 0.2, 'angular': -0.1}) == (0.2, -0.1)
    normalized = normalize_motion_payload({'type': 'cmd_vel', 'linear': 0.15, 'angular': 0.05})
    assert normalized['vx'] == 0.15
    assert normalized['wz'] == 0.05
    assert 'linear' not in normalized
    assert 'angular' not in normalized
