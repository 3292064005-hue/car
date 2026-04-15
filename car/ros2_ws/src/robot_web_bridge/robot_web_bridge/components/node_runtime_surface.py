from __future__ import annotations

from typing import Any, Callable, Mapping

from std_msgs.msg import String

from robot_contracts.bridge_contract import CommandContext, RuntimeParameterTransaction, command_capability_snapshot

from .ingress_service import IngressService
from .runtime_param_coordinator import RuntimeParamCoordinator


def build_link_health_snapshot(node: Any) -> dict[str, bool]:
    """Build a normalized link-health snapshot for command/runtime gating.

    Function:
        Derive one authoritative view of transport, board, heartbeat, and
        command-link readiness from the bridge node state.

    Args:
        node: Bridge node or a compatible test double exposing ``state``.

    Returns:
        A mapping with boolean fields:
        ``wifiTransportReady``, ``uartBoardReady``, ``motionHeartbeatReady``,
        and ``commandLinkReady``.

    Exceptions:
        None. Missing state structures are treated as empty mappings.

    Boundary behavior:
        ``commandLinkReady`` is intentionally strict. Wi-Fi transport, UART
        board connectivity, and motion heartbeat must all be healthy. This
        prevents ``wifi_ok`` from being treated as a sufficient write-path
        readiness signal.
    """
    state = getattr(node, 'state', None)
    status = dict(getattr(state, 'system_status', {}) or {})
    transport = dict(getattr(state, 'transport_stats', {}) or {})
    bridge = dict(getattr(state, 'bridge_summary', {}) or {})
    stale_flags = dict(getattr(state, 'stale_flags', {}) or {})

    wifi_transport_ready = bool(status.get('wifi_ok', False) and not stale_flags.get('transport', False))
    uart_board_ready = bool(status.get('uart_ok', False))
    motion_heartbeat_ready = bool(
        bridge.get('connected', False)
        and not stale_flags.get('bridge', False)
        and not stale_flags.get('chassis', False)
        and not transport.get('stale_link', False)
    )
    return {
        'wifiTransportReady': wifi_transport_ready,
        'uartBoardReady': uart_board_ready,
        'motionHeartbeatReady': motion_heartbeat_ready,
        'commandLinkReady': bool(wifi_transport_ready and uart_board_ready and motion_heartbeat_ready),
    }


def build_command_context(node: Any) -> CommandContext:
    """Build the command-guard context from current bridge state.

    Function:
        Translate the bridge node state into the contract-layer command context
        used by command capability evaluation.

    Args:
        node: Active bridge node.

    Returns:
        ``CommandContext`` populated from current state.

    Exceptions:
        None.

    Boundary behavior:
        ``bridge_connected`` now follows ``commandLinkReady`` from the unified
        link-health model rather than a permissive Wi-Fi fallback.
    """
    fault_level = str(node.state.fault.get('level', 'info') or 'info').lower()
    link_health = build_link_health_snapshot(node)
    return CommandContext(
        current_mode=node.state.mode,
        bridge_connected=bool(link_health['commandLinkReady']),
        low_power_warning=bool(node.state.power.get('lowPowerWarning', False) or node.state.system_status.get('low_power_warn', False) or node.state.system_status.get('low_power_stop', False)),
        fault_code=node.state.fault.get('code'),
        fault_level='critical' if fault_level in {'critical', 'fatal', 'error'} else 'warning' if fault_level in {'warning', 'warn'} else 'info',
        estop_active=bool(node.state.fault.get('estopActive', False)),
        safe_stop_active=bool(node.state.fault.get('safeStopActive', False)),
        safe_stop_recoverable=bool(node.state.contract_snapshot.get('safeStopRecoverable', node.state.fault.get('recoverable', True))),
        safe_stop_requires_manual_ack=bool(node.state.contract_snapshot.get('safeStopRequiresManualAck', False)),
        safe_stop_blocked_reason=node.state.contract_snapshot.get('safeStopBlockedReason'),
    )


def refresh_contract_snapshot(node: Any, summary_data: Mapping[str, Any] | None = None) -> None:
    if isinstance(summary_data, Mapping) and 'command_permissions' in summary_data:
        authoritative_mode = str(summary_data.get('mode', node.state.mode) or node.state.mode)
        node.state.contract_snapshot = {
            'allowedTargetModes': list(summary_data.get('allowed_target_modes', [])),
            'modeReasons': dict(summary_data.get('mode_reasons', {})),
            'commandPermissions': dict(summary_data.get('command_permissions', {})),
            'safeStopRecoverable': bool(summary_data.get('safe_stop_recoverable', True)),
            'safeStopRequiresManualAck': bool(summary_data.get('safe_stop_requires_manual_ack', False)),
            'safeStopBlockedReason': summary_data.get('safe_stop_blocked_reason'),
            'contractSource': str(summary_data.get('contract_source', 'robot_contracts.command_policy:command_capability_snapshot') or 'robot_contracts.command_policy:command_capability_snapshot'),
            'contractAuthority': str(summary_data.get('contract_authority', 'backend_authoritative') or 'backend_authoritative'),
        }
        node.state.contract_snapshot_authoritative = True
        node.state.contract_snapshot_mode = authoritative_mode
        return
    if node.state.contract_snapshot_authoritative and node.state.contract_snapshot_mode == node.state.mode:
        return
    node.state.contract_snapshot = command_capability_snapshot(build_command_context(node))
    node.state.contract_snapshot_authoritative = False
    node.state.contract_snapshot_mode = node.state.mode


def mutate_state_compat(instance: Any, callback: Callable[[Any], None]) -> None:
    store = getattr(instance, 'state_store', None)
    if store is not None:
        store.mutate(callback)
        return
    callback(instance.state)
    sync = getattr(instance, '_sync_snapshot_cache', None)
    if callable(sync):
        sync()


def record_trace_id_compat(instance: Any, trace_id: str) -> None:
    if not trace_id:
        return
    store = getattr(instance, 'state_store', None)
    if store is not None:
        store.record_trace_id(trace_id)
        return
    state = getattr(instance, 'state', None)
    if state is not None:
        setattr(state, 'last_trace_id', trace_id)
    sync = getattr(instance, '_sync_snapshot_cache', None)
    if callable(sync):
        sync()


def record_command_phase_compat(
    instance: Any,
    event_id: str,
    command_type: str,
    phase: str,
    status: str,
    message: str,
    *,
    trace_id: str = '',
    extra: Mapping[str, Any] | None = None,
) -> None:
    if hasattr(instance, 'record_command_phase'):
        instance.record_command_phase(event_id, command_type, phase, status, message, trace_id=trace_id, extra=extra)
        return
    record_trace_id_compat(instance, trace_id)
    timeline = getattr(getattr(instance, 'state', None), 'command_timeline', None)
    if timeline is None:
        return
    item = {
        'commandId': event_id,
        'commandType': command_type,
        'phase': phase,
        'status': status,
        'message': message,
        'traceId': trace_id or None,
        'ts': instance.now_iso() if hasattr(instance, 'now_iso') else '',
    }
    if extra:
        item.update(dict(extra))
    timeline.appendleft(item)
    sync = getattr(instance, '_sync_snapshot_cache', None)
    if callable(sync):
        sync()


def ingress_service(node: Any) -> IngressService:
    service = getattr(node, 'ingress_service', None)
    if service is None:
        service = IngressService(node=node)
        try:
            node.ingress_service = service
        except Exception:
            pass
    return service


def runtime_param_coordinator(node: Any) -> RuntimeParamCoordinator:
    coordinator = getattr(node, 'runtime_param_coordinator', None)
    if coordinator is None:
        coordinator = RuntimeParamCoordinator(node=node)
        try:
            node.runtime_param_coordinator = coordinator
        except Exception:
            pass
    return coordinator


def begin_runtime_param_transaction(node: Any, *, reason: str, trace_id: str = '') -> RuntimeParameterTransaction:
    return runtime_param_coordinator(node).begin_transaction(reason=reason, trace_id=trace_id)


def finalize_runtime_param_transaction(node: Any, *, state_label: str, message: str, ok: bool, trace_id: str = '') -> None:
    runtime_param_coordinator(node).finalize_transaction(state_label=state_label, message=message, ok=ok, trace_id=trace_id)


def consume_runtime_param_apply_result(node: Any, payload: Mapping[str, Any]) -> None:
    runtime_param_coordinator(node).consume_apply_result(payload)


def on_runtime_param_apply_result(node: Any, msg: String) -> None:
    runtime_param_coordinator(node).on_apply_result_message(msg)


def expire_runtime_param_transaction(node: Any) -> None:
    runtime_param_coordinator(node).expire_transaction()


def apply_runtime_param_update(
    node: Any,
    *,
    key: str,
    value: Any,
    trace_id: str = '',
    command_id: str = '',
    command_type: str = '',
) -> str:
    return runtime_param_coordinator(node).apply_update(
        key=key,
        value=value,
        trace_id=trace_id,
        command_id=command_id,
        command_type=command_type,
    )


def apply_runtime_param_draft(
    node: Any,
    *,
    params: Mapping[str, Any],
    trace_id: str = '',
    command_id: str = '',
    command_type: str = '',
) -> str:
    return runtime_param_coordinator(node).apply_patch(
        patch=params,
        trace_id=trace_id,
        command_id=command_id,
        command_type=command_type,
    )


def apply_runtime_param_profile(
    node: Any,
    *,
    profile_name: str,
    trace_id: str = '',
    command_id: str = '',
    command_type: str = '',
) -> str:
    return runtime_param_coordinator(node).apply_profile(
        profile_name=profile_name,
        trace_id=trace_id,
        command_id=command_id,
        command_type=command_type,
    )


def match_runtime_profile_name(node: Any, params: Mapping[str, Any]) -> str:
    return runtime_param_coordinator(node).match_profile_name(params)


def runtime_low_power_threshold(node: Any) -> float:
    return runtime_param_coordinator(node).runtime_low_power_threshold()


def publish_runtime_params(node: Any, *, reason: str, trace_id: str = '') -> None:
    runtime_param_coordinator(node).publish_runtime_params(reason=reason, trace_id=trace_id)


def refresh_stale_flags(node: Any) -> None:
    transport = node.state.transport_stats or node.state.bridge_summary
    system_status = node.state.system_status or {}
    motion = node.state.motion or {}
    voice = node.state.voice or {}
    battery_percent = node.state.power.get('batteryPercent')
    threshold = runtime_low_power_threshold(node)
    low_power_from_threshold = False
    try:
        if battery_percent is not None:
            low_power_from_threshold = float(battery_percent) <= threshold
    except (TypeError, ValueError):
        low_power_from_threshold = False
    node.state.stale_flags.update({
        'bridge': bool(transport.get('stale_link', False) or transport.get('state') in {'stale', 'reconnecting', 'disconnected'}),
        'transport': bool(transport.get('transport_degraded', False) or transport.get('state') in {'stale', 'reconnecting', 'disconnected'}),
        'vision': bool(not system_status.get('camera_ok', True)),
        'voice': bool(not system_status.get('audio_ok', True)),
        'power': bool(system_status.get('low_power_warn', False) or system_status.get('low_power_stop', False) or low_power_from_threshold),
        'chassis': bool(not system_status.get('uart_ok', True) or not motion.get('heartbeatOk', True) or node.state.fault.get('timeoutStopActive', False)),
    })
    voice_conf = float(voice.get('voiceConfidence', 1.0) or 0.0)
    if node.state.voice and voice.get('lastVoiceCommand') and voice_conf < 0.45:
        node.state.stale_flags['voice'] = True
    refresh_contract_snapshot(node)


def handle_ws_message(node: Any, raw: str):
    return ingress_service(node).handle_ws_message(raw)


def refresh_readiness(node: Any) -> None:
    snapshot = node.readiness_cache.refresh_all(timeout_sec=0.0)
    current = dict(node.state.transport_stats)
    current['dependencyReadiness'] = snapshot
    node.state_store.replace_mapping('transport_stats', current)


def on_transport_observation(node: Any, kind: str, **payload: Any) -> None:
    stats = dict(node.state.transport_stats)
    counters = {
        'queue_full': 'queue_full_count',
        'enqueue_failed': 'enqueue_failed_count',
        'client_dropped': 'client_drop_count',
        'client_cleanup_failed': 'client_cleanup_failed_count',
        'future_exception': 'future_exception_count',
        'client_connected': 'client_connected_count',
        'payload_budget_exceeded': 'payload_budget_exceeded_count',
        'payload_degraded': 'payload_degraded_count',
    }
    key = counters.get(kind)
    if key is not None:
        stats[key] = int(stats.get(key, 0) or 0) + 1
    if 'payload_bytes' in payload:
        payload_bytes = int(payload.get('payload_bytes', 0) or 0)
        stats['last_payload_bytes'] = payload_bytes
        stats['payload_bytes_total'] = int(stats.get('payload_bytes_total', 0) or 0) + payload_bytes
        lane = str(payload.get('lane', '') or 'unknown')
        lane_totals = dict(stats.get('payload_bytes_by_lane', {})) if isinstance(stats.get('payload_bytes_by_lane', {}), dict) else {}
        lane_totals[lane] = int(lane_totals.get(lane, 0) or 0) + payload_bytes
        stats['payload_bytes_by_lane'] = lane_totals
        if kind == 'payload_budget_exceeded':
            stats['last_budget_exceeded'] = {
                'event_type': str(payload.get('event_type', '') or 'telemetry'),
                'lane': lane,
                'payload_bytes': payload_bytes,
                'budget_bytes': int(payload.get('budget_bytes', 0) or 0),
                'ts': node.now_iso(),
            }
    stats['last_transport_observation'] = {'kind': kind, **payload, 'ts': node.now_iso()}
    node.state_store.replace_mapping('transport_stats', stats)


def on_dispatcher_observation(node: Any, kind: str, **payload: Any) -> None:
    stats = dict(node.state.transport_stats)
    counters = {
        'accepted': 'dispatcher_accept_count',
        'processed': 'dispatcher_process_count',
        'busy_rejected': 'dispatcher_busy_reject_count',
        'latest_only_replaced': 'dispatcher_latest_only_replace_count',
        'preempted': 'dispatcher_preempt_count',
    }
    key = counters.get(kind)
    if key is not None:
        stats[key] = int(stats.get(key, 0) or 0) + 1
    if payload:
        stats['last_dispatcher_observation'] = {'kind': kind, **payload, 'ts': node.now_iso()}
    node.state_store.replace_mapping('transport_stats', stats)
    sync_dispatcher_snapshot(node)


def sync_dispatcher_snapshot(node: Any) -> None:
    stats = dict(node.state.transport_stats)
    stats.update(node.dispatcher.stats_snapshot())
    node.state_store.replace_mapping('transport_stats', stats)


def process_command_queue(node: Any) -> None:
    node.dispatcher.process_batch(int(node.get_parameter('dispatch_batch_max').value))
    node.command_router.expire_pending()
    expire_runtime_param_transaction(node)
    sync_dispatcher_snapshot(node)


def publish_heartbeat(node: Any) -> None:
    node.state_store.set_attr('last_heartbeat_at', node.now_iso())
    node.schedule_send(node.envelopes.event('heartbeat', node.connection_payload()))
