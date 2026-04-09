#!/usr/bin/env python3
from __future__ import annotations

"""Resolve surface-specific runtime configuration into one artifact."""

import argparse
import os
import json
import yaml
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_bringup.config_resolution import resolve_bringup_config
from robot_bringup.launch_profiles import get_launch_profile, launch_profile_resolution
from robot_bringup.matrix_contracts import surface_contract_for_profile

SURFACE_CHOICES = ('backend', 'web_bridge', 'frontend')


def _load_api_server_auth(config_root: Path) -> dict[str, object]:
    source = config_root / 'api_server.yaml'
    if not source.is_file():
        return {}
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    config = payload.get('robot_api_server', payload) if isinstance(payload, dict) else {}
    auth = config.get('auth', {}) if isinstance(config, dict) and isinstance(config.get('auth', {}), dict) else {}
    upstream = auth.get('upstream_bridge_session', {}) if isinstance(auth.get('upstream_bridge_session', {}), dict) else {}
    operator_tokens = [str(item).strip() for item in auth.get('operator_tokens', []) if str(item).strip()]
    runtime_operator_token = str(os.environ.get('ROBOT_OPERATOR_TOKEN', '')).strip()
    if runtime_operator_token and runtime_operator_token not in operator_tokens:
        operator_tokens.append(runtime_operator_token)
    return {
        'default_role': str(auth.get('default_role', 'observer')).strip() or 'observer',
        'require_operator_token': bool(auth.get('require_operator_token', True)),
        'operator_tokens': operator_tokens,
        'upstream_bridge_session': {
            'role': str(upstream.get('role', 'operator')).strip() or 'operator',
            'session_id': str(upstream.get('session_id', 'robot-api-server')).strip() or 'robot-api-server',
            'token': str(upstream.get('token', '')).strip(),
        },
    }


def _frontend_default_session(*, profile_name: str, api_public_host: str, websocket_public_host: str, config_root: Path) -> dict[str, str]:
    auth = _load_api_server_auth(config_root)
    is_loopback_surface = api_public_host in {'127.0.0.1', 'localhost'} and websocket_public_host in {'127.0.0.1', 'localhost'}
    if not is_loopback_surface:
        return {'role': '', 'token': '', 'session_id': ''}
    upstream = auth.get('upstream_bridge_session', {}) if isinstance(auth.get('upstream_bridge_session', {}), dict) else {}
    token = str(upstream.get('token', '') or '')
    if not token:
        tokens = auth.get('operator_tokens', []) if isinstance(auth.get('operator_tokens', []), list) else []
        token = str(tokens[0]) if tokens else ''
    return {
        'role': 'operator' if token else str(auth.get('default_role', 'observer') or 'observer'),
        'token': token,
        'session_id': f'{profile_name}-frontend',
    }

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Resolve inspection-robot startup config for one surface.')
    parser.add_argument('--profile', default='mock')
    parser.add_argument('--surface', choices=SURFACE_CHOICES, required=True)
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--output', default='')
    parser.add_argument('--emit-shell', action='store_true')
    return parser.parse_args()


def build_payload(*, profile_name: str, surface: str, config_path: str | None, output_path: str = '') -> dict[str, object]:
    resolved = resolve_bringup_config(config_path)
    profile = get_launch_profile(profile_name, config_path=config_path)
    runtime = profile.runtime()
    bridge_host = '127.0.0.1' if surface == 'frontend' else runtime.bridge.host
    websocket_public_host = profile.websocket_public_host or ('127.0.0.1' if surface == 'frontend' else runtime.bridge.host)
    websocket_listen_host = profile.websocket_listen_host or '0.0.0.0'
    websocket_port = int(profile.websocket_port)
    websocket_path = str(profile.websocket_path or '/ws')
    if not websocket_path.startswith('/'):
        websocket_path = '/' + websocket_path.lstrip('/')
    api_public_host = getattr(profile, 'api_server_public_host', None) or websocket_public_host
    api_listen_host = getattr(profile, 'api_server_listen_host', None) or '0.0.0.0'
    api_probe_host = api_public_host if api_public_host not in {'0.0.0.0', '::', '::0', '*'} else '127.0.0.1'
    api_port = int(getattr(profile, 'api_server_port', 9100))
    api_ws_path = str(getattr(profile, 'api_server_ws_path', '/ws') or '/ws')
    if not api_ws_path.startswith('/'):
        api_ws_path = '/' + api_ws_path.lstrip('/')
    api_prefix = str(getattr(profile, 'api_server_api_prefix', '/api/v1') or '/api/v1')
    if not api_prefix.startswith('/'):
        api_prefix = '/' + api_prefix.lstrip('/')
    bridge_ws_url = f'ws://{websocket_public_host}:{websocket_port}{websocket_path}'
    api_ws_url = f'ws://{api_public_host}:{api_port}{api_ws_path}'
    api_health_url = f'http://{api_probe_host}:{api_port}{api_prefix}/health'
    ws_url = api_ws_url if surface == 'frontend' and getattr(profile, 'enable_api_server', False) else bridge_ws_url
    mjpeg_url = runtime.bridge.mjpeg_url or ''
    frontend_session = _frontend_default_session(profile_name=profile.name, api_public_host=api_public_host, websocket_public_host=websocket_public_host, config_root=resolved.config_root)
    contract_path = ''
    if output_path:
        output = Path(output_path)
        contract_path = str(output.with_suffix('.json'))
    return {
        'surface': surface,
        'profile': profile.name,
        'configResolution': {
            'configRoot': str(resolved.config_root),
            'launchProfilesPath': str(resolved.launch_profiles_path),
            'rawInput': resolved.raw_input,
            'source': resolved.source,
        },
        'launchProfileResolution': launch_profile_resolution(config_path),
        'profileSnapshot': profile.to_dict(),
        'runtimeSurface': {
            'bridgeHost': bridge_host,
            'bridgePort': int(runtime.bridge.port),
            'websocketUrl': ws_url,
            'bridgeWebsocketUrl': bridge_ws_url,
            'apiWebsocketUrl': api_ws_url,
            'websocketPublicHost': websocket_public_host,
            'websocketListenHost': websocket_listen_host,
            'websocketPort': websocket_port,
            'websocketPath': websocket_path,
            'apiServerPublicHost': api_public_host,
            'apiServerListenHost': api_listen_host,
            'apiServerPort': api_port,
            'apiServerWsPath': api_ws_path,
            'apiServerApiPrefix': api_prefix,
            'apiProbeHost': api_probe_host,
            'apiHealthUrl': api_health_url,
            'operatorSurfaceContract': surface_contract_for_profile(profile).get('frontend', {}),
            'mjpegUrl': mjpeg_url,
            'contractArtifactPath': contract_path,
        },
        'frontendEnv': {
            'VITE_ROBOT_WS_URL': ws_url,
            'VITE_ROBOT_BRIDGE_WS_URL': bridge_ws_url,
            'VITE_ROBOT_API_WS_URL': api_ws_url,
            'VITE_ROBOT_API_BASE_URL': f'http://{api_public_host}:{api_port}{api_prefix}',
            'VITE_ROBOT_MJPEG_URL': mjpeg_url,
            'VITE_ENABLE_MOCK': 'false',
            'VITE_BRIDGE_LABEL': f'{profile.name}-{surface}',
            'VITE_ROBOT_SESSION_ROLE': frontend_session['role'] if surface == 'frontend' else '',
            'VITE_ROBOT_SESSION_TOKEN': frontend_session['token'] if surface == 'frontend' else '',
            'VITE_ROBOT_SESSION_ID': frontend_session['session_id'] if surface == 'frontend' else '',
        },
        'runtimeEnv': {
            'ROBOT_EFFECTIVE_CONFIG_ROOT': str(resolved.config_root),
            'ROBOT_EFFECTIVE_LAUNCH_PROFILES_PATH': str(resolved.launch_profiles_path),
            'ROBOT_EFFECTIVE_PROFILE': profile.name,
            'ROBOT_EFFECTIVE_SURFACE': surface,
            'ROBOT_EFFECTIVE_BRIDGE_HOST': bridge_host,
            'ROBOT_EFFECTIVE_BRIDGE_PORT': str(runtime.bridge.port),
            'ROBOT_EFFECTIVE_MJPEG_URL': mjpeg_url,
            'ROBOT_EFFECTIVE_WS_URL': ws_url,
            'ROBOT_EFFECTIVE_BRIDGE_WS_URL': bridge_ws_url,
            'ROBOT_EFFECTIVE_API_WS_URL': api_ws_url,
            'ROBOT_EFFECTIVE_API_BASE_URL': f'http://{api_public_host}:{api_port}{api_prefix}',
            'ROBOT_EFFECTIVE_API_HEALTH_URL': api_health_url,
            'ROBOT_EFFECTIVE_WS_PUBLIC_HOST': websocket_public_host,
            'ROBOT_EFFECTIVE_WS_LISTEN_HOST': websocket_listen_host,
            'ROBOT_EFFECTIVE_WS_PORT': str(websocket_port),
            'ROBOT_EFFECTIVE_WS_PATH': websocket_path,
            'ROBOT_EFFECTIVE_API_SERVER_PUBLIC_HOST': api_public_host,
            'ROBOT_EFFECTIVE_API_SERVER_LISTEN_HOST': api_listen_host,
            'ROBOT_EFFECTIVE_API_SERVER_PORT': str(api_port),
            'ROBOT_EFFECTIVE_API_SERVER_WS_PATH': api_ws_path,
            'ROBOT_EFFECTIVE_API_SERVER_API_PREFIX': api_prefix,
            'ROBOT_RUNTIME_SURFACE_CONTRACT_PATH': contract_path,
            'ROBOT_EFFECTIVE_FRONTEND_SESSION_ROLE': frontend_session['role'] if surface == 'frontend' else '',
            'ROBOT_EFFECTIVE_FRONTEND_SESSION_ID': frontend_session['session_id'] if surface == 'frontend' else '',
        },
    }


def emit_shell(payload: dict[str, object]) -> str:
    lines: list[str] = []
    for key, value in payload['runtimeEnv'].items():
        lines.append(f"export {key}={json.dumps(str(value), ensure_ascii=False)}")
    if payload['surface'] == 'frontend':
        for key, value in payload['frontendEnv'].items():
            lines.append(f"export {key}={json.dumps(str(value), ensure_ascii=False)}")
    return '\n'.join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(profile_name=args.profile, surface=args.surface, config_path=args.config_path or None, output_path=args.output)
    text = emit_shell(payload) if args.emit_shell else json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + ('\n' if not text.endswith('\n') else ''), encoding='utf-8')
        contract_path = path.with_suffix('.json')
        contract_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
