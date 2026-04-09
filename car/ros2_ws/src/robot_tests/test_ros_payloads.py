from types import SimpleNamespace

from robot_web_bridge.ros_payloads import chassis_payload, decision_task_payload, fault_payload, log_payload


def test_chassis_payload_maps_control_source():
    msg = SimpleNamespace(linear_velocity=0.2, angular_velocity=0.1, left_rpm=12.0, right_rpm=13.0, control_source='manual', heartbeat_ok=True)
    payload = chassis_payload(msg, '2026-03-31T00:00:00Z')
    assert payload['commandSource'] == 'ui'
    assert payload['leftWheelSpeed'] == 12.0
    assert payload['staleMotion'] is False


def test_fault_payload_normalizes_levels_and_flags():
    msg = SimpleNamespace(level='error', code='ESTOP', description='latched', recoverable=False)
    payload = fault_payload(msg, '2026-03-31T00:00:00Z', estop_active=True, timeout_stop_active=False, mode='SAFE_STOP')
    assert payload['level'] == 'critical'
    assert payload['safeStopActive'] is True
    assert payload['estopActive'] is True
    assert payload['latched'] is True
    assert 'Inspect' in payload['recommendedAction'] or 'clear' in payload['recommendedAction']


def test_log_payload_maps_domain_and_level():
    msg = SimpleNamespace(level='warn', category='vision', name='target_lost', detail='frame dropped')
    payload = log_payload(msg, '2026-03-31T00:00:00Z')
    assert payload['level'] == 'WARN'
    assert payload['domain'] == 'VISION'
    assert 'vision:target_lost' == payload['message']


def test_decision_task_payload_tracks_completion():
    payload = decision_task_payload({'patrol_completed': True, 'patrol_index': 3, 'current_step_name': 'WP-03'}, 'PATROL', 'previous')
    assert payload['patrolStatus'] == 'completed'
    assert payload['completedPoints'] == 3
