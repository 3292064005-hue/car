from __future__ import annotations

"""Runtime contract and config loader for the standard read-only observability bridge."""

from pathlib import Path
from urllib.parse import urlsplit
from typing import Any, Iterable, Mapping

import yaml

READONLY_TOPICS = (
    '/robot/bridge/summary',
    '/robot/decision/summary',
    '/robot/control/summary',
    '/robot/navigation/status',
    '/robot/runtime/supervision',
)
SUPPORTED_BRIDGE_FAMILIES = ('disabled', 'repo_readonly_websocket', 'rosbridge_suite', 'foxglove_bridge', 'custom_command')
RUNTIME_ENFORCED_BRIDGE_FAMILIES: tuple[str, ...] = ('repo_readonly_websocket',)
EXTERNAL_REFERENCE_BRIDGE_FAMILIES: tuple[str, ...] = ('rosbridge_suite', 'foxglove_bridge')
OBSERVABILITY_WRITE_POLICY = 'read_only_no_operator_commands'
OBSERVABILITY_INTROSPECTION_CAPABILITIES = ('topic_list', 'schema_metadata', 'node_graph', 'message_sample', 'subscription_audit')


def _normalize_list(items: Iterable[Any] | None) -> tuple[str, ...]:
    values: list[str] = []
    for item in items or ():
        normalized = str(item or '').strip()
        if normalized:
            values.append(normalized)
    return tuple(values)


def _default_bridge_command(*, bridge_family: str, listen_host: str, port: int, ws_path: str, readonly_topics: Iterable[Any] | None = None, upstream_url: str = 'ws://127.0.0.1:9001/ws') -> tuple[str, ...]:
    if bridge_family == 'repo_readonly_websocket':
        command = ['python3', '-m', 'robot_web_bridge.standard_observability_bridge_runtime', '--listen-host', str(listen_host), '--port', str(int(port)), '--ws-path', str(ws_path), '--upstream-url', str(upstream_url)]
        for topic in _normalize_list(readonly_topics):
            command.extend(['--readonly-topic', topic])
        return tuple(command)
    if bridge_family == 'rosbridge_suite':
        return ('ros2', 'launch', 'rosbridge_server', 'rosbridge_websocket_launch.xml', f'address:={listen_host}', f'port:={int(port)}')
    if bridge_family == 'foxglove_bridge':
        return ('ros2', 'run', 'foxglove_bridge', 'foxglove_bridge')
    return ()


def _command_tuple(command_override: Iterable[Any] | None, *, bridge_family: str, listen_host: str, port: int, ws_path: str, readonly_topics: Iterable[Any] | None = None, upstream_url: str = 'ws://127.0.0.1:9001/ws') -> tuple[str, ...]:
    normalized = _normalize_list(command_override)
    if bridge_family == 'custom_command' and normalized:
        return normalized
    return _default_bridge_command(bridge_family=bridge_family, listen_host=listen_host, port=port, ws_path=ws_path, readonly_topics=readonly_topics, upstream_url=upstream_url)


def load_standard_observability_bridge_params(config_root: str | Path | None) -> dict[str, Any]:
    root = Path(str(config_root or '').strip()) if config_root else None
    source = root / 'bridge.yaml' if root else None
    if source is None or not source.is_file():
        return {}
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    config = payload.get('robot_bridge', payload) if isinstance(payload, dict) else {}
    ros_params = config.get('ros__parameters', {}) if isinstance(config, dict) and isinstance(config.get('ros__parameters', {}), dict) else {}
    return {
        'enabled': bool(ros_params.get('enable_standard_observability_bridge', False)),
        'bridge_family': str(ros_params.get('standard_observability_bridge_family', 'disabled') or 'disabled').strip() or 'disabled',
        'listen_host': str(ros_params.get('standard_observability_bridge_listen_host', '127.0.0.1') or '127.0.0.1').strip() or '127.0.0.1',
        'port': int(ros_params.get('standard_observability_bridge_port', 8765) or 8765),
        'ws_path': str(ros_params.get('standard_observability_bridge_ws_path', '/observability') or '/observability').strip() or '/observability',
        'require_localhost': bool(ros_params.get('standard_observability_bridge_require_localhost', True)),
        'readonly_topics': _normalize_list(ros_params.get('standard_observability_bridge_readonly_topics', READONLY_TOPICS)) or READONLY_TOPICS,
        'command_override': _normalize_list(ros_params.get('standard_observability_bridge_command', ())),
        'upstream_url': str(ros_params.get('standard_observability_bridge_upstream_url', 'ws://127.0.0.1:9001/ws') or 'ws://127.0.0.1:9001/ws').strip() or 'ws://127.0.0.1:9001/ws',
    }


def standard_observability_bridge_contract(*, enabled: bool = False, bridge_family: str = 'disabled', listen_host: str = '127.0.0.1', port: int = 8765, ws_path: str = '/observability', require_localhost: bool = True, readonly_topics: Iterable[Any] = READONLY_TOPICS, command_override: Iterable[Any] | None = None, upstream_url: str = 'ws://127.0.0.1:9001/ws') -> dict[str, Any]:
    normalized_family = str(bridge_family or 'disabled').strip() or 'disabled'
    if normalized_family not in SUPPORTED_BRIDGE_FAMILIES:
        normalized_family = 'custom_command'
    normalized_ws_path = str(ws_path or '/observability').strip() or '/observability'
    if not normalized_ws_path.startswith('/'):
        normalized_ws_path = '/' + normalized_ws_path.lstrip('/')
    requested_enabled = bool(enabled and normalized_family != 'disabled')
    if requested_enabled and require_localhost and listen_host not in {'127.0.0.1', 'localhost'}:
        raise ValueError('standard observability bridge must stay on localhost when require_localhost=true')
    upstream_host = str(urlsplit(str(upstream_url)).hostname or '').strip()
    if requested_enabled and upstream_host not in {'127.0.0.1', 'localhost'}:
        raise ValueError('standard observability bridge upstream_url must point to localhost observer surface')
    runtime_launch_permitted = bool(requested_enabled and normalized_family in RUNTIME_ENFORCED_BRIDGE_FAMILIES)
    command = _command_tuple(command_override, bridge_family=normalized_family, listen_host=listen_host, port=int(port), ws_path=normalized_ws_path, readonly_topics=readonly_topics, upstream_url=upstream_url) if runtime_launch_permitted else ()
    normalized_topics = _normalize_list(readonly_topics) or READONLY_TOPICS
    if requested_enabled and not runtime_launch_permitted:
        status = 'contract_only_pending_readonly_enforcement'
        launch_mode = 'policy_blocked'
        policy_reason = 'runtime_family_not_repo_audited_readonly_proxy'
    else:
        status = 'repo_audited_readonly_proxy_runtime' if runtime_launch_permitted else 'disabled_by_default'
        launch_mode = 'repo_audited_proxy' if runtime_launch_permitted else 'disabled'
        policy_reason = 'not_applicable'
    return {
        'contractVersion': '2.1.0',
        'status': status,
        'enabled': runtime_launch_permitted,
        'requestedEnabled': requested_enabled,
        'runtimeLaunchPermitted': runtime_launch_permitted,
        'writeIngressAllowed': False,
        'writePolicy': OBSERVABILITY_WRITE_POLICY,
        'introspectionCapabilities': list(OBSERVABILITY_INTROSPECTION_CAPABILITIES),
        'authorityBoundary': '9100_api_facade_only',
        'bridgeFamily': normalized_family,
        'suggestedBridgeFamilies': ['repo_readonly_websocket'],
        'externalReferenceBridgeFamilies': list(EXTERNAL_REFERENCE_BRIDGE_FAMILIES),
        'readonlyTopics': list(normalized_topics),
        'uiExposurePolicy': 'debug_only_hidden_by_default',
        'listenHost': str(listen_host),
        'port': int(port),
        'wsPath': normalized_ws_path,
        'requireLocalhost': bool(require_localhost),
        'launchCommand': list(command),
        'launchMode': launch_mode,
        'policyReason': policy_reason,
        'protocol': 'inspection_robot.readonly_bridge.v1' if runtime_launch_permitted else 'contract_only',
        'allowedClientOps': ['ping', 'list_topics', 'subscribe', 'unsubscribe'] if runtime_launch_permitted else [],
        'upstreamUrl': str(upstream_url),
    }


def resolve_standard_observability_bridge_contract(config_root: str | Path | None) -> dict[str, Any]:
    params = load_standard_observability_bridge_params(config_root)
    return standard_observability_bridge_contract(enabled=bool(params.get('enabled', False)), bridge_family=str(params.get('bridge_family', 'disabled') or 'disabled'), listen_host=str(params.get('listen_host', '127.0.0.1') or '127.0.0.1'), port=int(params.get('port', 8765) or 8765), ws_path=str(params.get('ws_path', '/observability') or '/observability'), require_localhost=bool(params.get('require_localhost', True)), readonly_topics=params.get('readonly_topics', READONLY_TOPICS), command_override=params.get('command_override', ()), upstream_url=str(params.get('upstream_url', 'ws://127.0.0.1:9001/ws') or 'ws://127.0.0.1:9001/ws'))
