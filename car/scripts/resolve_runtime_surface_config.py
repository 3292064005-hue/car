#!/usr/bin/env python3
from __future__ import annotations

"""Resolve one surface-specific runtime configuration artifact.

This module is intentionally side-effect free. It only reads profile/config/env
state and emits a deterministic runtime contract. Any runtime bootstrap work
(secrets, socket directories, local operator-session injection) must happen
*after* this resolver finishes so the startup contract stays auditable.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from robot_bringup.config_resolution import resolve_bringup_config
from robot_contracts.lane_registry import lane_registry_payload
from robot_contracts.signal_ownership import governance_signal_registry_payload
from robot_bringup.launch_profiles import get_launch_profile, launch_profile_resolution
from robot_bringup.matrix_contracts import profile_feature_matrix, surface_contract_for_profile
from robot_navigation.provider_contract import navigation_provider_activation
from runtime_surface_inventory import load_hardware_boundary_snapshot

SURFACE_CHOICES = ('backend', 'web_bridge', 'frontend')
_LOOPBACK_HOSTS = {'127.0.0.1', 'localhost'}
_OPERATOR_SESSION_BOOTSTRAP_MODES = {'auto', 'disabled', 'external', 'required'}


def _loopback_surface(*, api_public_host: str, websocket_public_host: str) -> bool:
    """Return whether both public endpoints are loopback-only.

    Args:
        api_public_host: Effective API public host.
        websocket_public_host: Effective bridge websocket public host.

    Returns:
        ``True`` when both public endpoints stay on the local machine.

    Raises:
        None.
    """
    return api_public_host in _LOOPBACK_HOSTS and websocket_public_host in _LOOPBACK_HOSTS



def _load_api_server_auth(config_root: Path) -> dict[str, object]:
    """Load API-server session defaults without mutating runtime state.

    Args:
        config_root: Bringup configuration root.

    Returns:
        Normalized auth mapping. Missing config files yield an empty mapping.

    Raises:
        None.
    """
    source = config_root / 'api_server.yaml'
    if not source.is_file():
        return {}
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    config = payload.get('robot_api_server', payload) if isinstance(payload, dict) else {}
    auth = config.get('auth', {}) if isinstance(config, dict) and isinstance(config.get('auth', {}), dict) else {}
    upstream = auth.get('upstream_bridge_session', {}) if isinstance(auth.get('upstream_bridge_session', {}), dict) else {}
    operator_tokens = [str(item).strip() for item in auth.get('operator_tokens', []) if str(item).strip()]
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





def _load_navigation_provider_contract(config_root: Path) -> dict[str, object]:
    """Load the configured navigation-provider activation contract.

    Args:
        config_root: Bringup configuration root.

    Returns:
        Serializable provider-activation payload. Missing files fall back to the
        default simple provider contract.

    Raises:
        ValueError: If the configured provider name is unsupported.
    """
    source = config_root / 'navigation.yaml'
    if not source.is_file():
        return navigation_provider_activation('simple_nav_provider')
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    config = payload.get('robot_navigation', payload) if isinstance(payload, dict) else {}
    ros_params = config.get('ros__parameters', {}) if isinstance(config, dict) and isinstance(config.get('ros__parameters', {}), dict) else {}
    provider_name = str(ros_params.get('provider_name', 'simple_nav_provider') or 'simple_nav_provider').strip() or 'simple_nav_provider'
    return navigation_provider_activation(provider_name)

def _operator_session_bootstrap_mode(*, surface: str, deployment_tier: str, api_public_host: str, websocket_public_host: str) -> str:
    """Return the operator-session bootstrap mode for the requested surface.

    Args:
        surface: Requested surface name.
        deployment_tier: Effective deployment tier from the launch profile.
        api_public_host: Effective API public host.
        websocket_public_host: Effective bridge websocket public host.

    Returns:
        One of ``disabled``, ``external``, ``local_auto`` or ``required``.

    Raises:
        ValueError: If the environment requests an unsupported mode.
    """
    requested = str(os.environ.get('ROBOT_OPERATOR_SESSION_BOOTSTRAP_MODE', 'auto') or 'auto').strip().lower()
    if requested not in _OPERATOR_SESSION_BOOTSTRAP_MODES:
        raise ValueError(
            'ROBOT_OPERATOR_SESSION_BOOTSTRAP_MODE must be one of '
            f'{sorted(_OPERATOR_SESSION_BOOTSTRAP_MODES)}; got {requested!r}'
        )
    if surface != 'frontend':
        return 'disabled'
    if requested == 'disabled':
        return 'disabled'
    if requested == 'external':
        return 'external'
    if requested == 'required':
        return 'required'
    if _loopback_surface(api_public_host=api_public_host, websocket_public_host=websocket_public_host) and deployment_tier == 'host_harness':
        return 'local_auto'
    return 'external'



def _frontend_default_session(
    *,
    profile_name: str,
    api_public_host: str,
    websocket_public_host: str,
    config_root: Path,
    operator_session_bootstrap_mode: str,
) -> dict[str, str]:
    """Resolve the frontend's initial session bootstrap snapshot.

    Args:
        profile_name: Effective launch profile name.
        api_public_host: API public host.
        websocket_public_host: Bridge websocket public host.
        config_root: Bringup configuration root.
        operator_session_bootstrap_mode: Resolver-selected bootstrap mode.

    Returns:
        Frontend session bootstrap mapping.

    Raises:
        None.
    """
    auth = _load_api_server_auth(config_root)
    is_loopback = _loopback_surface(api_public_host=api_public_host, websocket_public_host=websocket_public_host)
    if operator_session_bootstrap_mode in {'disabled', 'external'}:
        return {'role': '', 'token': '', 'session_id': ''}
    if operator_session_bootstrap_mode == 'local_auto':
        return {
            'role': str(auth.get('default_role', 'observer') or 'observer'),
            'token': '',
            'session_id': f'{profile_name}-frontend',
        }
    if not is_loopback and operator_session_bootstrap_mode != 'required':
        return {'role': '', 'token': '', 'session_id': ''}
    upstream = auth.get('upstream_bridge_session', {}) if isinstance(auth.get('upstream_bridge_session', {}), dict) else {}
    token = str(upstream.get('token', '') or '')
    if not token:
        tokens = auth.get('operator_tokens', []) if isinstance(auth.get('operator_tokens', []), list) else []
        token = str(tokens[0]) if tokens else ''
    role = 'operator' if token else str(auth.get('default_role', 'observer') or 'observer')
    return {
        'role': role,
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
    """Build one side-effect-free runtime surface payload.

    Args:
        profile_name: Effective launch profile name.
        surface: Surface identifier.
        config_path: Optional bringup config root or launch_profiles path.
        output_path: Optional artifact output path used only to precompute the
            sidecar JSON contract path.

    Returns:
        Serializable runtime-surface payload.

    Raises:
        ValueError: If session bootstrap mode resolution is invalid.
    """
    resolved = resolve_bringup_config(config_path)
    profile = get_launch_profile(profile_name, config_path=config_path)
    runtime = profile.runtime()
    deployment_tier = profile.deployment_tier()
    hardware_boundary_mode = profile.hardware_boundary_mode()
    hardware_boundary = load_hardware_boundary_snapshot(resolved.config_root)
    navigation_provider = _load_navigation_provider_contract(resolved.config_root)
    capability_snapshot = profile_feature_matrix(profile, config_path=config_path)
    bridge_host = '127.0.0.1' if surface == 'frontend' else runtime.bridge.host
    websocket_public_host = profile.websocket_public_host or ('127.0.0.1' if surface == 'frontend' else runtime.bridge.host)
    websocket_listen_host = profile.websocket_listen_host or ('127.0.0.1' if surface == 'frontend' else '0.0.0.0')
    websocket_port = int(profile.websocket_port)
    websocket_path = str(profile.websocket_path or '/ws')
    if not websocket_path.startswith('/'):
        websocket_path = '/' + websocket_path.lstrip('/')
    api_public_host = getattr(profile, 'api_server_public_host', None) or websocket_public_host
    api_listen_host = getattr(profile, 'api_server_listen_host', None) or ('127.0.0.1' if surface == 'frontend' else '0.0.0.0')
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
    operator_session_bootstrap_mode = _operator_session_bootstrap_mode(
        surface=surface,
        deployment_tier=deployment_tier,
        api_public_host=api_public_host,
        websocket_public_host=websocket_public_host,
    )
    frontend_session = _frontend_default_session(
        profile_name=profile.name,
        api_public_host=api_public_host,
        websocket_public_host=websocket_public_host,
        config_root=resolved.config_root,
        operator_session_bootstrap_mode=operator_session_bootstrap_mode,
    )
    frontend_session_contract_stage = 'not_applicable'
    frontend_session_effective_source = 'not_applicable'
    if surface == 'frontend':
        frontend_session_contract_stage = 'pre_bootstrap'
        if operator_session_bootstrap_mode in {'local_auto', 'required'}:
            frontend_session_effective_source = 'runtime_bootstrap'
        elif operator_session_bootstrap_mode == 'external':
            frontend_session_effective_source = 'external_client'
        else:
            frontend_session_effective_source = 'disabled'
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
            'operatorSurfaceContract': surface_contract_for_profile(profile, config_path=config_path).get('frontend', {}),
            'operatorSessionBootstrapMode': operator_session_bootstrap_mode,
            'deploymentTier': deployment_tier,
            'hardwareBoundaryMode': hardware_boundary_mode,
            'hardwareBoundary': hardware_boundary,
            'capabilitySnapshot': capability_snapshot,
            'navigationProvider': navigation_provider,
            'navigationRuntimePackage': navigation_provider.get('governanceLane', {}).get('packageName', ''),
            'hardwareRuntimePackage': hardware_boundary.get('governanceLane', {}).get('packageName', ''),
            'laneRegistry': lane_registry_payload(include_experimental=True),
            'signalOwnershipRegistry': governance_signal_registry_payload(),
            'frontendSessionContractStage': frontend_session_contract_stage,
            'frontendSessionEffectiveSource': frontend_session_effective_source,
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
            'VITE_ROBOT_SESSION_MODE': operator_session_bootstrap_mode if surface == 'frontend' else '',
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
            'ROBOT_EFFECTIVE_DEPLOYMENT_TIER': deployment_tier,
            'ROBOT_EFFECTIVE_HARDWARE_BOUNDARY_MODE': hardware_boundary_mode,
            'ROBOT_EFFECTIVE_HARDWARE_SURFACE_ROLE': str(hardware_boundary['compatibilitySurfaceRole']),
            'ROBOT_EFFECTIVE_BOARD_VALIDATION_IN_REPO': str(hardware_boundary['boardValidationInRepo']).lower(),
            'ROBOT_EFFECTIVE_BOARD_EXECUTION_CONFIRMED': str(hardware_boundary['boardExecutionConfirmed']).lower(),
            'ROBOT_EFFECTIVE_HARDWARE_TRANSPORT_AUTHORITY': str(hardware_boundary['transportAuthority']),
            'ROBOT_EFFECTIVE_HARDWARE_VERIFICATION_STAGE': str(hardware_boundary['verificationStage']),
            'ROBOT_EFFECTIVE_HARDWARE_COMMAND_TRANSPORT': str(hardware_boundary['commandTransport']),
            'ROBOT_EFFECTIVE_HARDWARE_EVIDENCE_CLASS': str(hardware_boundary['executionEvidenceClass']),
            'ROBOT_EFFECTIVE_HARDWARE_ACTIVATION': str(hardware_boundary.get('activationDecision', 'activate')),
            'ROBOT_EFFECTIVE_HARDWARE_REJECTION_REASON': str(hardware_boundary.get('rejectionReason', '')),
            'ROBOT_EFFECTIVE_NAVIGATION_PROVIDER': str(navigation_provider['resolvedProvider']['providerName']),
            'ROBOT_EFFECTIVE_NAVIGATION_PROVIDER_PACKAGE': str(navigation_provider.get('governanceLane', {}).get('packageName', '')),
            'ROBOT_EFFECTIVE_NAVIGATION_PROVIDER_ACTIVATION': str(navigation_provider['activationDecision']),
            'ROBOT_EFFECTIVE_HARDWARE_PACKAGE': str(hardware_boundary.get('governanceLane', {}).get('packageName', '')),
            'ROBOT_EFFECTIVE_OPERATOR_SESSION_BOOTSTRAP_MODE': operator_session_bootstrap_mode,
            'ROBOT_RUNTIME_SURFACE_CONTRACT_PATH': contract_path,
            'ROBOT_EFFECTIVE_FRONTEND_SESSION_ROLE': frontend_session['role'] if surface == 'frontend' else '',
            'ROBOT_EFFECTIVE_FRONTEND_SESSION_ID': frontend_session['session_id'] if surface == 'frontend' else '',
        },
    }



def emit_shell(payload: dict[str, object]) -> str:
    """Render shell exports for the runtime payload.

    Args:
        payload: Result of :func:`build_payload`.

    Returns:
        Shell export script text.

    Raises:
        KeyError: If the payload is malformed.
    """
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
