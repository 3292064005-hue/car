from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path

from robot_monitor.status_aggregator import StatusSnapshot, derive_health
from robot_utils.constants import HEALTH_DEGRADED


@dataclass
class Metrics:
    events_logged: int = 0
    event_log_write_successes: int = 0
    event_log_write_failures: int = 0
    faults_seen: int = 0
    qrcodes_seen: int = 0
    voice_cmd_seen: int = 0
    voice_reject_count: int = 0
    snapshots_saved: int = 0
    summaries_published: int = 0
    reconnect_count: int = 0
    protocol_errors: int = 0
    command_timeout_count: int = 0
    safe_stop_count: int = 0
    frame_drop_count: int = 0
    average_rtt_ms: float = 0.0
    health_transitions: int = 0
    last_health: str = HEALTH_DEGRADED

    def health(self, snapshot: StatusSnapshot) -> str:
        health = derive_health(snapshot)
        if health != self.last_health:
            self.health_transitions += 1
            self.last_health = health
        return health

    def dump_json(self, filepath: str) -> None:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding='utf-8')
