from __future__ import annotations

from robot_web_bridge.web_bridge_node import RobotWebBridgeNode


class _Param:
    def __init__(self, value):
        self.value = value


class _StubNode:
    def __init__(self):
        self._params = {
            'default_session_role': 'observer',
        }

    def get_parameter(self, name: str):
        return _Param(self._params[name])


def test_direct_bridge_client_stays_read_only_even_with_operator_token() -> None:
    stub = _StubNode()
    policy = RobotWebBridgeNode.resolve_gateway_session_policy(stub, {
        'remote_address': {'host': '203.0.113.7', 'port': 50123},
        'query': {
            'role': 'operator',
            'token': 'local-operator-token',
            'sessionId': 'browser-client',
        }
    })
    assert policy['role'] == 'observer'
    assert policy['write_enabled'] is False
    assert policy['source'] == 'bridge_direct_readonly'


def test_loopback_bridge_client_still_stays_read_only() -> None:
    stub = _StubNode()
    policy = RobotWebBridgeNode.resolve_gateway_session_policy(stub, {
        'remote_address': {'host': '127.0.0.1', 'port': 50124},
        'query': {
            'role': 'operator',
            'sessionId': 'robot-api-server',
        }
    })
    assert policy['role'] == 'observer'
    assert policy['write_enabled'] is False
    assert policy['source'] == 'bridge_direct_readonly'


def test_direct_bridge_client_cannot_escalate_with_internal_bridge_token_query() -> None:
    stub = _StubNode()
    policy = RobotWebBridgeNode.resolve_gateway_session_policy(stub, {
        'remote_address': {'host': '203.0.113.9', 'port': 50125},
        'query': {
            'role': 'operator',
            'sessionId': 'forged-upstream',
            'bridgeClientToken': 'forged-token',
        }
    })
    assert policy['role'] == 'observer'
    assert policy['write_enabled'] is False
    assert policy['source'] == 'bridge_direct_readonly'


def test_bridge_observer_surface_overlay_is_projected_into_connection_payload() -> None:
    connection = RobotWebBridgeNode._apply_session_policy_to_connection(
        {'commandPermissions': {'set_mode': {'allowed': True}}},
        type('Policy', (), {
            'role': 'observer',
            'requested_role': 'operator',
            'write_enabled': False,
            'reason': 'direct bridge sessions are observer-only; command writes are blocked',
            'session_id': 'browser-client',
            'source': 'bridge_direct_readonly',
        })(),
    )
    assert connection['surfaceId'] == 'bridge_observer_surface'
    assert connection['surfaceWriteEnabled'] is False
    assert 'observability_report' in connection['surfaceLayers']
    assert connection['commandPermissions']['set_mode']['allowed'] is False
