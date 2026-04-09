from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping


@dataclass(slots=True)
class ProbeState:
    """Cached readiness state for one dependency probe."""

    ready: bool = False
    last_checked_at: str | None = None
    error: str | None = None


class ReadinessCache:
    """Background cache for service/action readiness probes.

    Request handlers should only consume this cache; active probing belongs in a
    background timer so user commands are not blocked by repeated wait calls.
    """

    def __init__(self, *, checks: Mapping[str, Callable[[float], bool]], logger: Any | None = None) -> None:
        self._checks = dict(checks)
        self._logger = logger
        self._states = {name: ProbeState() for name in self._checks}

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def refresh(self, name: str, *, timeout_sec: float = 0.0) -> ProbeState:
        """Refresh one readiness probe.

        Args:
            name: Logical dependency name.
            timeout_sec: Probe timeout passed to the checker.

        Returns:
            Updated :class:`ProbeState` snapshot.

        Raises:
            KeyError: If ``name`` is unknown.
        """
        if name not in self._checks:
            raise KeyError(name)
        state = self._states[name]
        try:
            state.ready = bool(self._checks[name](timeout_sec))
            state.error = None
        except Exception as exc:
            state.ready = False
            state.error = str(exc)
            if self._logger is not None:
                self._logger.warning(f'readiness probe failed for {name}: {exc}')
        state.last_checked_at = self._now_iso()
        return ProbeState(ready=state.ready, last_checked_at=state.last_checked_at, error=state.error)

    def refresh_all(self, *, timeout_sec: float = 0.0) -> dict[str, dict[str, Any]]:
        """Refresh all registered readiness probes.

        Args:
            timeout_sec: Probe timeout passed to each checker.

        Returns:
            Serializable readiness snapshot.

        Raises:
            None.
        """
        for name in self._checks:
            self.refresh(name, timeout_sec=timeout_sec)
        return self.snapshot()

    def is_ready(self, name: str) -> bool:
        """Return the cached readiness bit for one dependency.

        Args:
            name: Logical dependency name.

        Returns:
            Cached readiness bit.

        Raises:
            KeyError: If ``name`` is unknown.
        """
        if name not in self._states:
            raise KeyError(name)
        return bool(self._states[name].ready)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return the current cached readiness snapshot."""
        return {
            name: {
                'ready': state.ready,
                'lastCheckedAt': state.last_checked_at,
                'error': state.error,
            }
            for name, state in self._states.items()
        }
