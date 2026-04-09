from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from robot_contracts.bridge_contract import RuntimeParameterState


@dataclass
class WebBridgeState:
    mode: str = 'BOOT'
    previous_mode: str = 'BOOT'
    requested_by: str = 'system'
    motion: dict[str, Any] = field(default_factory=lambda: {'mode': 'BOOT'})
    power: dict[str, Any] = field(default_factory=dict)
    vision: dict[str, Any] = field(default_factory=dict)
    voice: dict[str, Any] = field(default_factory=dict)
    task: dict[str, Any] = field(default_factory=dict)
    fault: dict[str, Any] = field(default_factory=lambda: {
        'level': 'info',
        'code': None,
        'message': None,
        'safeStopActive': False,
        'estopActive': False,
        'timeoutStopActive': False,
        'recoverable': True,
        'recommendedAction': None,
        'lastUpdateAt': None,
    })
    bridge_summary: dict[str, Any] = field(default_factory=dict)
    transport_stats: dict[str, Any] = field(default_factory=dict)
    system_status: dict[str, Any] = field(default_factory=dict)
    reports: dict[str, Any] = field(default_factory=dict)
    stale_flags: dict[str, bool] = field(default_factory=lambda: {
        'bridge': False,
        'vision': False,
        'voice': False,
        'power': False,
        'chassis': False,
        'transport': False,
    })
    logs: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=80))
    recent_voice_commands: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=12))
    qrcode_history: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=12))
    command_audit: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=40))
    command_timeline: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=60))
    runtime_params: RuntimeParameterState = field(default_factory=RuntimeParameterState)
    contract_snapshot: dict[str, Any] = field(default_factory=dict)
    contract_snapshot_authoritative: bool = False
    contract_snapshot_mode: str = 'BOOT'
    operator_ready: bool = False
    operator_ready_reasons: list[str] = field(default_factory=lambda: ['gateway_not_started'])
    operator_ready_topic: str | None = None
    last_heartbeat_at: str | None = None
    last_trace_id: str | None = None

    def snapshot(self, *, mjpeg_url: str, connection: dict[str, Any]) -> dict[str, Any]:
        vision = dict(self.vision)
        vision.setdefault('streamUrl', mjpeg_url)
        vision['qrcodeHistory'] = list(self.qrcode_history)
        voice = dict(self.voice)
        voice['recentCommands'] = list(self.recent_voice_commands)
        return {
            'connection': connection,
            'motion': dict(self.motion),
            'power': dict(self.power),
            'vision': vision,
            'voice': voice,
            'task': dict(self.task),
            'fault': dict(self.fault),
            'reports': dict(self.reports),
            'params': dict(self.runtime_params.params),
            'paramMetadata': self.runtime_params.metadata(),
            'transport': dict(self.transport_stats),
            'staleFlags': dict(self.stale_flags),
            'logs': list(self.logs)[-20:],
            'commandAudit': list(self.command_audit)[-20:],
            'commandTimeline': list(self.command_timeline)[-30:],
            'paramApply': self.runtime_params.last_transaction.metadata(),
        }
