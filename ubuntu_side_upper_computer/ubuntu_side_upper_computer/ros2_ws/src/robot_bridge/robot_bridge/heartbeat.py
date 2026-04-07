from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass
class HeartbeatTracker:
    last_tx: float = 0.0
    last_rx: float = 0.0
    pending: dict[int, float] = field(default_factory=dict)
    last_rtt_ms: float = 0.0

    def mark_tx(self, seq: int | None = None) -> None:
        now = time.monotonic()
        self.last_tx = now
        if seq is not None:
            self.pending[seq] = now

    def mark_rx(self, seq: int | None = None) -> None:
        now = time.monotonic()
        self.last_rx = now
        if seq is not None and seq in self.pending:
            self.last_rtt_ms = (now - self.pending.pop(seq)) * 1000.0

    def age(self) -> float:
        if self.last_rx == 0.0:
            return float('inf')
        return time.monotonic() - self.last_rx
