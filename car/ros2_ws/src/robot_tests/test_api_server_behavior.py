from __future__ import annotations

from robot_api_server.proxy_server import RobotApiProxyServer


def test_health_payload_requires_upstream_and_operator_ready() -> None:
    server = RobotApiProxyServer(upstream_url='ws://127.0.0.1:9001/ws', listen_host='127.0.0.1', listen_port=9100)
    server.mirror.connected = True
    server.mirror.latest_connection = {
        'operatorReady': True,
        'operatorReadyReasons': [],
        'operatorReadyTopic': '/robot/web_bridge/ready',
        'runtimeHealthState': 'ready',
        'runtimeHealthReasons': [],
    }
    payload = server._health_payload()
    assert payload['ok'] is True
    assert payload['ready'] is True
    assert payload['operatorReady'] is True
    assert payload['runtimeHealthState'] == 'ready'
    assert payload['sessionRole'] == 'observer'
    assert payload['sessionWriteEnabled'] is False


def test_health_payload_reports_not_ready_when_operator_surface_missing() -> None:
    server = RobotApiProxyServer(upstream_url='ws://127.0.0.1:9001/ws', listen_host='127.0.0.1', listen_port=9100)
    server.mirror.connected = False
    server.mirror.latest_connection = {'operatorReady': False, 'runtimeHealthState': 'unavailable'}
    payload = server._health_payload()
    assert payload['ok'] is False
    assert payload['ready'] is False
    assert payload['operatorReady'] is False
    assert 'operator_surface_not_ready' in payload['operatorReadyReasons']
    assert 'api_upstream_disconnected' in payload['runtimeHealthReasons']


def test_readonly_policy_overlays_command_permissions() -> None:
    server = RobotApiProxyServer(upstream_url='ws://127.0.0.1:9001/ws', listen_host='127.0.0.1', listen_port=9100)
    policy = server._resolve_policy(requested_role='observer', session_id='view-only', source='request')
    payload = server._overlay_command_permissions({'allowedTargetModes': ['MANUAL'], 'commandPermissions': {'set_mode': {'allowed': True}}}, policy)
    assert payload['allowedTargetModes'] == []
    assert payload['commandPermissions']['set_mode']['allowed'] is False
    assert payload['sessionRole'] == 'observer'
    assert payload['sessionWriteEnabled'] is False


def test_operator_request_without_valid_token_downgrades_to_observer() -> None:
    server = RobotApiProxyServer(
        upstream_url='ws://127.0.0.1:9001/ws',
        listen_host='127.0.0.1',
        listen_port=9100,
        require_operator_token=True,
        operator_tokens=('alpha',),
    )
    policy = server._resolve_policy(requested_role='operator', token='wrong', session_id='s1', source='request')
    assert policy.role == 'observer'
    assert policy.write_enabled is False
    assert 'downgraded' in policy.reason
