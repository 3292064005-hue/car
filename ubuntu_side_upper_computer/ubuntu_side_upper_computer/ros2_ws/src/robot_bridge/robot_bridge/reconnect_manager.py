from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class ReconnectManager:
    min_period_sec: float
    max_period_sec: float = 8.0
    multiplier: float = 1.8
    current_period_sec: float = 0.0
    last_attempt: float = 0.0
    last_result: str = 'idle'

    def __post_init__(self) -> None:
        self.min_period_sec = max(0.05, float(self.min_period_sec))
        self.max_period_sec = max(self.min_period_sec, float(self.max_period_sec))
        self.multiplier = max(1.1, float(self.multiplier))
        self.current_period_sec = self.min_period_sec

    def should_retry(self) -> bool:
        now = time.monotonic()
        if now - self.last_attempt >= self.current_period_sec:
            self.last_attempt = now
            self.last_result = 'attempting'
            return True
        return False

    def mark_result(self, success: bool) -> None:
        self.last_result = 'connected' if success else 'backoff'
        if success:
            self.current_period_sec = self.min_period_sec
            return
        self.current_period_sec = min(self.max_period_sec, self.current_period_sec * self.multiplier)

    def next_retry_in_sec(self) -> float:
        remaining = self.current_period_sec - (time.monotonic() - self.last_attempt)
        return round(max(0.0, remaining), 3)

    def summary(self) -> dict[str, float | str]:
        return {
            'reconnect_state': self.last_result,
            'reconnect_backoff_sec': round(self.current_period_sec, 3),
            'reconnect_retry_in_sec': self.next_retry_in_sec(),
        }
