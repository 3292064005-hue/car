from __future__ import annotations

from pathlib import Path

from robot_api_server.api_server_main import _load_config_defaults


def test_load_api_server_defaults_from_yaml(tmp_path: Path) -> None:
    config = tmp_path / 'api_server.yaml'
    config.write_text(
        'robot_api_server:\n'
        '  listen_host: 192.168.4.10\n'
        '  listen_port: 9200\n'
        '  ws_path: /robot/ws\n'
        '  api_prefix: /robot/api\n'
        '  auth:\n'
        '    default_role: observer\n'
        '    require_operator_token: true\n'
        '    operator_tokens: [alpha, beta]\n',
        encoding='utf-8',
    )
    defaults = _load_config_defaults(str(config))
    assert defaults == {
        'listen_host': '192.168.4.10',
        'listen_port': 9200,
        'ws_path': '/robot/ws',
        'api_prefix': '/robot/api',
        'auth': {
            'default_role': 'observer',
            'require_operator_token': True,
            'operator_tokens': ['alpha', 'beta'],
            'upstream_bridge_session': {
                'role': 'observer',
                'session_id': 'robot-api-server-mirror',
                'token': '',
                'internal_command_socket_path': '/tmp/inspection_robot/bridge_internal_command.sock',
                'internal_command_auth_token': '',
            },
        },
    }
