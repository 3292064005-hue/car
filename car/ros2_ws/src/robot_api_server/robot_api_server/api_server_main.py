from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import yaml

from .proxy_server import RobotApiProxyServer


def _normalize_auth_defaults(config: dict[str, object]) -> dict[str, object]:
    auth = config.get('auth', {}) if isinstance(config.get('auth', {}), dict) else {}
    operator_tokens = auth.get('operator_tokens', [])
    if not isinstance(operator_tokens, list):
        raise ValueError('robot_api_server.auth.operator_tokens must be a list')
    normalized_tokens = [str(item).strip() for item in operator_tokens if str(item).strip()]
    runtime_operator_token = str(os.environ.get('ROBOT_OPERATOR_TOKEN', '')).strip()
    if runtime_operator_token and runtime_operator_token not in normalized_tokens:
        normalized_tokens.append(runtime_operator_token)
    default_role = str(auth.get('default_role', 'observer')).strip() or 'observer'
    require_operator_token = bool(auth.get('require_operator_token', True))
    upstream_auth = auth.get('upstream_bridge_session', {}) if isinstance(auth.get('upstream_bridge_session', {}), dict) else {}
    upstream_role = str(upstream_auth.get('role', 'observer')).strip() or 'observer'
    upstream_session_id = str(upstream_auth.get('session_id', 'robot-api-server-mirror')).strip() or 'robot-api-server-mirror'
    upstream_token = str(upstream_auth.get('token', '')).strip()
    internal_command_socket_path = str(os.environ.get('ROBOT_INTERNAL_COMMAND_SOCKET_PATH', upstream_auth.get('internal_command_socket_path', '/tmp/inspection_robot/bridge_internal_command.sock'))).strip() or '/tmp/inspection_robot/bridge_internal_command.sock'
    internal_command_auth_token = str(os.environ.get('ROBOT_INTERNAL_COMMAND_AUTH_TOKEN', upstream_auth.get('internal_command_auth_token', ''))).strip()
    return {
        'default_role': default_role,
        'require_operator_token': require_operator_token,
        'operator_tokens': normalized_tokens,
        'upstream_bridge_session': {
            'role': upstream_role,
            'session_id': upstream_session_id,
            'token': upstream_token,
            'internal_command_socket_path': internal_command_socket_path,
            'internal_command_auth_token': internal_command_auth_token,
        },
    }


def _load_config_defaults(config_file: str | None) -> dict[str, object]:
    """Load API-server defaults from one YAML file.

    Args:
        config_file: Optional YAML path containing a ``robot_api_server`` mapping.

    Returns:
        Normalized CLI default mapping. Missing files and empty payloads return an
        empty mapping so the caller can still rely on CLI defaults.

    Raises:
        ValueError: If the YAML payload is not a mapping.
    """
    if not config_file:
        return {}
    source = Path(config_file)
    if not source.is_file():
        raise FileNotFoundError(f'api server config not found: {source}')
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    if not isinstance(payload, dict):
        raise ValueError('api server config payload must be a mapping')
    config = payload.get('robot_api_server', payload)
    if not isinstance(config, dict):
        raise ValueError('robot_api_server config section must be a mapping')
    return {
        'listen_host': str(config.get('listen_host', '127.0.0.1')).strip() or '127.0.0.1',
        'listen_port': int(config.get('listen_port', 9100)),
        'ws_path': str(config.get('ws_path', '/ws')).strip() or '/ws',
        'api_prefix': str(config.get('api_prefix', '/api/v1')).strip() or '/api/v1',
        'auth': _normalize_auth_defaults(config),
    }


def build_parser(defaults: dict[str, object] | None = None) -> argparse.ArgumentParser:
    defaults = defaults or {}
    auth_defaults = defaults.get('auth', {}) if isinstance(defaults.get('auth', {}), dict) else {}
    parser = argparse.ArgumentParser(description='Inspection robot API facade for frontend clients.')
    parser.add_argument('--config-file', default='')
    parser.add_argument('--listen-host', default=str(defaults.get('listen_host', '127.0.0.1')))
    parser.add_argument('--listen-port', type=int, default=int(defaults.get('listen_port', 9100)))
    parser.add_argument('--ws-path', default=str(defaults.get('ws_path', '/ws')))
    parser.add_argument('--api-prefix', default=str(defaults.get('api_prefix', '/api/v1')))
    parser.add_argument('--default-role', default=str(auth_defaults.get('default_role', 'observer')))
    parser.add_argument('--require-operator-token', action='store_true', default=bool(auth_defaults.get('require_operator_token', True)))
    parser.add_argument('--operator-token', action='append', default=list(auth_defaults.get('operator_tokens', [])), help='Operator token allowed to request writable API sessions. Can be repeated.')
    upstream_defaults = auth_defaults.get('upstream_bridge_session', {}) if isinstance(auth_defaults.get('upstream_bridge_session', {}), dict) else {}
    parser.add_argument('--upstream-session-role', default=str(upstream_defaults.get('role', 'observer')))
    parser.add_argument('--upstream-session-id', default=str(upstream_defaults.get('session_id', 'robot-api-server-mirror')))
    parser.add_argument('--upstream-session-token', default=str(upstream_defaults.get('token', '')))
    parser.add_argument('--internal-command-socket-path', default=str(upstream_defaults.get('internal_command_socket_path', '/tmp/inspection_robot/bridge_internal_command.sock')))
    parser.add_argument('--internal-command-auth-token', default=str(upstream_defaults.get('internal_command_auth_token', '')))
    parser.add_argument('--upstream-url', required=True)
    return parser


async def _run_async(args: argparse.Namespace) -> None:
    server = RobotApiProxyServer(
        upstream_url=args.upstream_url,
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        ws_path=args.ws_path,
        api_prefix=args.api_prefix,
        default_role=args.default_role,
        require_operator_token=bool(args.require_operator_token),
        operator_tokens=tuple(str(item).strip() for item in (args.operator_token or []) if str(item).strip()),
        upstream_session_role=args.upstream_session_role,
        upstream_session_id=args.upstream_session_id,
        upstream_session_token=args.upstream_session_token,
        internal_command_socket_path=args.internal_command_socket_path,
        internal_command_auth_token=args.internal_command_auth_token,
    )
    await server.start()
    try:
        while True:
            await asyncio.sleep(3600.0)
    finally:
        await server.stop()


def main() -> None:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument('--config-file', default='')
    bootstrap_args, remaining = bootstrap.parse_known_args()
    parser = build_parser(_load_config_defaults(bootstrap_args.config_file or None))
    args = parser.parse_args(remaining)
    args.config_file = bootstrap_args.config_file
    asyncio.run(_run_async(args))


if __name__ == '__main__':  # pragma: no cover
    main()
