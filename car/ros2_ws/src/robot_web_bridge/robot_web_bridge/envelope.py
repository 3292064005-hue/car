from __future__ import annotations

from typing import Any

from robot_contracts.bridge_contract import BRIDGE_CAPABILITIES, CommandAck, PROTOCOL_VERSION, SCHEMA_VERSION, make_envelope, now_iso

from .state_model import WebBridgeState


class EnvelopeFactory:
    def __init__(self, *, session_id: str = 'robot-web-bridge') -> None:
        self.session_id = session_id
        self.seq = 0

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def event(self, event_type: str, payload: dict[str, Any], *, source: str = 'bridge', trace_id: str | None = None) -> dict[str, Any]:
        return make_envelope(event_type, payload, source=source, session_id=self.session_id, seq=self.next_seq(), trace_id=trace_id)

    def ack(
        self,
        command_id: str,
        status: str,
        message: str,
        *,
        detail: str = '',
        trace_id: str | None = None,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]:
        return self.event(
            'command_ack',
            CommandAck(
                command_id=command_id,
                status=status,
                message=message,
                detail=detail,
                trace_id=trace_id or '',
                lifecycle_status=lifecycle_status or '',
            ).to_payload(),
            trace_id=trace_id,
        )



def build_connection_payload(state: WebBridgeState) -> dict[str, Any]:
    bridge = state.bridge_summary
    transport = state.transport_stats or bridge
    status = state.system_status
    now = now_iso()
    stale_flags = state.stale_flags
    transport_state = str(transport.get('state') or bridge.get('state') or 'disconnected')
    transport_degraded = bool(transport.get('transport_degraded', False) or stale_flags.get('transport', False))
    bridge_connected = bool(bridge.get('connected', False))
    contract_snapshot = dict(state.contract_snapshot or {})
    stale_motion = bool(stale_flags.get('bridge', False) or stale_flags.get('chassis', False) or transport.get('stale_link', False))
    stale_power = bool(stale_flags.get('power', False) or (status.get('low_power_warn', False) and status.get('uart_ok', True)))
    stale_vision = bool(stale_flags.get('vision', False) or not status.get('camera_ok', False))
    stale_voice = bool(stale_flags.get('voice', False) or not status.get('audio_ok', False))
    runtime_health_reasons: list[str] = []
    if not bridge_connected:
        runtime_health_reasons.append('bridge_disconnected')
    if transport_degraded:
        runtime_health_reasons.append('transport_degraded')
    if stale_motion:
        runtime_health_reasons.append('motion_stale')
    if stale_power:
        runtime_health_reasons.append('power_stale_or_low_power')
    if stale_vision:
        runtime_health_reasons.append('vision_stale_or_unavailable')
    if stale_voice:
        runtime_health_reasons.append('voice_stale_or_unavailable')
    if not status.get('uart_ok', False):
        runtime_health_reasons.append('uart_unavailable')
    runtime_supervision = state.reports.get('runtimeSupervision', {}) if isinstance(state.reports, dict) else {}
    runtime_supervision_parsed = runtime_supervision.get('parsed') if isinstance(runtime_supervision, dict) else None
    supervision_state = str(runtime_supervision_parsed.get('state', '') or '') if isinstance(runtime_supervision_parsed, dict) else ''
    supervision_reasons = [str(item) for item in runtime_supervision_parsed.get('reasons', [])] if isinstance(runtime_supervision_parsed, dict) and isinstance(runtime_supervision_parsed.get('reasons', []), list) else []
    if supervision_state == 'ready':
        runtime_health_state = 'ready'
        runtime_health_reasons = supervision_reasons or ['runtime_supervisor_ready']
    elif supervision_state == 'degraded':
        runtime_health_state = 'degraded'
        runtime_health_reasons = supervision_reasons or runtime_health_reasons
    elif supervision_state in {'unavailable', 'faulted'}:
        runtime_health_state = 'unavailable'
        runtime_health_reasons = supervision_reasons or runtime_health_reasons
    elif not bridge_connected or not status.get('uart_ok', False):
        runtime_health_state = 'unavailable'
    elif runtime_health_reasons:
        runtime_health_state = 'degraded'
    else:
        runtime_health_state = 'ready'
    operator_ready = bool(state.operator_ready)
    operator_ready_reasons = list(state.operator_ready_reasons or (['gateway_not_started'] if not operator_ready else []))
    return {
        'rosConnected': True,
        'bridgeConnected': bridge_connected,
        'stm32Connected': bool(status.get('uart_ok', False)),
        'videoConnected': bool(status.get('camera_ok', False)),
        'voiceConnected': bool(status.get('audio_ok', False)),
        'reconnecting': transport_state == 'reconnecting' or (not bridge_connected and transport_degraded),
        'latencyMs': float(bridge.get('last_rtt_ms', 0.0) or 0.0),
        'heartbeatAgeMs': float(bridge.get('heartbeat_age_sec', 0.0) or 0.0) * 1000.0,
        'lastHeartbeatAt': state.last_heartbeat_at or now,
        'transportLabel': transport_state,
        'transportType': 'websocket',
        'reconnectAttempts': int(bridge.get('reconnect_count', 0) or 0),
        'staleMotion': stale_motion,
        'stalePower': stale_power,
        'staleVision': stale_vision,
        'staleVoice': stale_voice,
        'inboundRateHz': float(transport.get('inbound_rate_hz', 0.0) or 0.0),
        'outboundRateHz': float(transport.get('outbound_rate_hz', 0.0) or 0.0),
        'protocolVersion': PROTOCOL_VERSION,
        'schemaVersion': SCHEMA_VERSION,
        'capabilities': list(BRIDGE_CAPABILITIES),
        'lastSnapshotVersion': SCHEMA_VERSION,
        'lastTraceId': state.last_trace_id,
        'compatibilityMode': 'native-v4',
        'allowedTargetModes': contract_snapshot.get('allowedTargetModes', []),
        'modeReasons': contract_snapshot.get('modeReasons', {}),
        'commandPermissions': contract_snapshot.get('commandPermissions', {}),
        'safeStopRecoverable': contract_snapshot.get('safeStopRecoverable', True),
        'safeStopRequiresManualAck': contract_snapshot.get('safeStopRequiresManualAck', False),
        'safeStopBlockedReason': contract_snapshot.get('safeStopBlockedReason'),
        'runtimeHealthState': runtime_health_state,
        'runtimeHealthReasons': runtime_health_reasons,
        'operatorReady': operator_ready,
        'operatorReadyReasons': operator_ready_reasons,
        'operatorReadyTopic': state.operator_ready_topic,
    }
