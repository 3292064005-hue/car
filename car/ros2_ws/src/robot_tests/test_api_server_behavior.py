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
    assert payload['surfaceId'] == 'frontend_api_facade'
    assert payload['surfaceWriteEnabled'] is True
    assert payload['surfaceAuthorityModel'] == 'authoritative_write_via_api_server_session_policy'


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


def test_command_denied_payload_uses_governed_detail_codes() -> None:
    server = RobotApiProxyServer(
        upstream_url='ws://127.0.0.1:9001/ws',
        listen_host='127.0.0.1',
        listen_port=9100,
        require_operator_token=True,
        operator_tokens=('alpha',),
    )
    policy = server._resolve_policy(requested_role='operator', token='wrong', session_id='s1', source='request')
    payload = server._command_denied_payload({'eventId': 'cmd-1', 'type': 'set_mode'}, policy)
    assert payload['payload']['detail'] == 'readonly_session'


def test_set_mode_denial_payload_keeps_machine_detail_code_for_mode_guard() -> None:
    from robot_contracts.command_policy import CommandContext, command_guard

    guard = command_guard('set_mode', CommandContext(current_mode='PATROL'), payload={'mode': 'TRACK'})
    assert guard.ok is False
    assert guard.detail_code == 'mode_transition_guard_rejected'



def test_product_interface_payload_exposes_single_robot_contract() -> None:
    server = RobotApiProxyServer(upstream_url='ws://127.0.0.1:9001/ws', listen_host='127.0.0.1', listen_port=9100, config_root='ros2_ws/src/robot_bringup/config')
    payload = server._product_interface_payload()
    assert payload['deploymentModel'] == 'single_robot_only'
    assert payload['httpEndpoints']['productInterface'] == '/api/v1/product-interface'
    assert payload['singleRobotPolicy']['multiRobotSchedulingAllowed'] is False


def test_missions_payload_exposes_default_mission_catalog() -> None:
    server = RobotApiProxyServer(upstream_url='ws://127.0.0.1:9001/ws', listen_host='127.0.0.1', listen_port=9100, config_root='ros2_ws/src/robot_bringup/config')
    payload = server._missions_payload()
    assert payload['deploymentModel'] == 'single_robot_only'
    assert payload['defaultMissionId'] == 'default_patrol'
    assert 'dock_then_patrol' in payload['missions']
