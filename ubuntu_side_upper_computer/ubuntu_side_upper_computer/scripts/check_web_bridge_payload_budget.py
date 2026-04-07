#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))
        nested = pkg / pkg.name
        if nested.is_dir():
            sys.path.insert(0, str(nested))

from robot_web_bridge.envelope import EnvelopeFactory
from robot_web_bridge.payload_budget import (
    DEFAULT_CONTROL_PAYLOAD_BUDGET_BYTES,
    DEFAULT_SNAPSHOT_PAYLOAD_BUDGET_BYTES,
    DEFAULT_TELEMETRY_PAYLOAD_BUDGET_BYTES,
    envelope_size_bytes,
    resolve_payload_budget,
)
from robot_web_bridge.state_model import WebBridgeState


def _sample_state() -> WebBridgeState:
    state = WebBridgeState(mode='PATROL', previous_mode='IDLE', requested_by='operator')
    state.motion.update({'mode': 'PATROL', 'linearVelocityMps': 0.18, 'angularVelocityRadps': 0.05})
    state.power.update({'batteryPercent': 63.0, 'batteryVoltage': 11.8, 'lowPowerWarning': False})
    state.vision.update({'targetType': 'apriltag', 'streamUrl': 'http://127.0.0.1:8080/stream', 'confidence': 0.91})
    state.voice.update({'lastCommand': 'resume_patrol', 'confidence': 0.98})
    state.task.update({'patrolStatus': 'running', 'trackEnabled': False, 'lastTaskEvent': '巡检运行中'})
    state.fault.update({'level': 'info', 'message': None, 'recoverable': True})
    state.transport_stats.update({'connected': True, 'state': 'active', 'payload_bytes_total': 2048})
    state.system_status.update({'wifi_ok': True, 'camera_ok': True, 'audio_ok': True, 'uart_ok': True})
    for index in range(20):
        state.logs.append({'category': 'system', 'message': f'log-{index}-bridge steady state', 'level': 'info'})
        state.command_audit.append({'commandId': f'cmd-{index}', 'status': 'accepted', 'message': 'ok'})
    for index in range(12):
        state.recent_voice_commands.append({'command': f'voice-{index}', 'confidence': 0.9, 'timestamp': f'2026-04-02T00:00:{index:02d}Z'})
        state.qrcode_history.append({'qrcodeText': f'QR-{index:02d}', 'detectTimestamp': f'2026-04-02T00:00:{index:02d}Z'})
    state.runtime_params.params.update({'control.max_linear_speed': 0.25, 'vision.track.confidence': 0.6})
    return state


def _measure(factory: EnvelopeFactory, event_type: str, payload: dict[str, object]) -> dict[str, object]:
    envelope = factory.event(event_type, payload)
    size = envelope_size_bytes(envelope)
    lane, budget = resolve_payload_budget(event_type)
    return {
        'type': event_type,
        'lane': lane,
        'bytes': size,
        'budget_bytes': budget,
        'within_budget': size <= budget,
    }


def main() -> int:
    state = _sample_state()
    factory = EnvelopeFactory(session_id='budget-check')
    snapshot = _measure(factory, 'snapshot', state.snapshot(mjpeg_url='http://127.0.0.1:8080/stream', connection={'bridgeConnected': True, 'transportType': 'websocket'}))
    heartbeat = _measure(factory, 'heartbeat', {'bridgeConnected': True, 'latencyMs': 12.0})
    task_event = _measure(factory, 'task_event', {'patrolStatus': 'running', 'lastTaskEvent': '巡检运行中'})
    report = {
        'budgets': {
            'telemetry_bytes': DEFAULT_TELEMETRY_PAYLOAD_BUDGET_BYTES,
            'control_bytes': DEFAULT_CONTROL_PAYLOAD_BUDGET_BYTES,
            'snapshot_bytes': DEFAULT_SNAPSHOT_PAYLOAD_BUDGET_BYTES,
        },
        'samples': [snapshot, heartbeat, task_event],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    failures = [item for item in report['samples'] if not item['within_budget']]
    if failures:
        raise SystemExit('web bridge payload budget exceeded')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
