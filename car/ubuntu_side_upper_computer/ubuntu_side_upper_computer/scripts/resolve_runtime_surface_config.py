#!/usr/bin/env python3
from __future__ import annotations

"""Resolve surface-specific runtime configuration into one artifact."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_bringup.config_resolution import resolve_bringup_config
from robot_bringup.launch_profiles import get_launch_profile, launch_profile_resolution

SURFACE_CHOICES = ('backend', 'web_bridge', 'frontend')

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
    ws_url = f'ws://{websocket_public_host}:{websocket_port}{websocket_path}'
    mjpeg_url = runtime.bridge.mjpeg_url or ''
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
            'websocketPublicHost': websocket_public_host,
            'websocketListenHost': websocket_listen_host,
            'websocketPort': websocket_port,
            'websocketPath': websocket_path,
            'mjpegUrl': mjpeg_url,
            'contractArtifactPath': contract_path,
        },
        'frontendEnv': {
            'VITE_ROBOT_WS_URL': ws_url,
            'VITE_ROBOT_MJPEG_URL': mjpeg_url,
            'VITE_ENABLE_MOCK': 'true' if profile.use_mock_robot else 'false',
            'VITE_BRIDGE_LABEL': f'{profile.name}-{surface}',
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
            'ROBOT_EFFECTIVE_WS_PUBLIC_HOST': websocket_public_host,
            'ROBOT_EFFECTIVE_WS_LISTEN_HOST': websocket_listen_host,
            'ROBOT_EFFECTIVE_WS_PORT': str(websocket_port),
            'ROBOT_EFFECTIVE_WS_PATH': websocket_path,
            'ROBOT_RUNTIME_SURFACE_CONTRACT_PATH': contract_path,
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
