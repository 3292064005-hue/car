from __future__ import annotations

from dataclasses import dataclass
import threading
import time


@dataclass
class FramePacket:
    frame: object | None = None
    stamp: float = 0.0
    sequence: int = 0


class FrameBuffer:
    """Thread-safe latest-frame container used across capture, vision and snapshot paths."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.latest = FramePacket()

    def update(self, frame: object) -> None:
        """Replace the latest frame packet.

        Args:
            frame: Newly captured frame-like object.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            The buffer stores only the most recent frame. Older frames are intentionally
            discarded to preserve latest-frame semantics under bursty capture rates.
        """
        with self._lock:
            sequence = self.latest.sequence + 1
            self.latest = FramePacket(frame=self._clone_frame(frame), stamp=time.monotonic(), sequence=sequence)

    def get(self, *, copy_frame: bool = True) -> FramePacket:
        """Read the current latest frame snapshot.

        Args:
            copy_frame: When ``True`` and the frame supports ``copy()``, return a detached
                clone so callers can annotate or persist without mutating shared state.

        Returns:
            Immutable ``FramePacket`` snapshot.

        Raises:
            None.
        """
        with self._lock:
            frame = self._clone_frame(self.latest.frame) if copy_frame else self.latest.frame
            return FramePacket(frame=frame, stamp=self.latest.stamp, sequence=self.latest.sequence)

    @staticmethod
    def _clone_frame(frame: object | None) -> object | None:
        if frame is None:
            return None
        copy_method = getattr(frame, 'copy', None)
        if callable(copy_method):
            try:
                return copy_method()
            except Exception:
                return frame
        return frame
