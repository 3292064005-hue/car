from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
import threading
import time
from typing import Any

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None

from robot_utils.helpers import slugify


class SnapshotSaveError(RuntimeError):
    """Raised when a snapshot cannot be persisted to disk."""


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    success: bool
    filepath: str = ''
    error: str = ''
    prefix: str = ''


class SnapshotManager:
    """Persist captured vision frames to disk with optional async offload."""

    def __init__(self, output_dir: str, *, async_queue_max: int = 16) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._request_queue: Queue[tuple[object, str] | None] = Queue(maxsize=max(1, int(async_queue_max)))
        self._result_queue: Queue[SnapshotResult] = Queue()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._worker_main, daemon=True)
        self._worker.start()

    def save(self, frame: object, prefix: str) -> str:
        """Save one frame to disk synchronously and return the resulting path.

        Args:
            frame: OpenCV-compatible image buffer.
            prefix: Human-readable filename prefix.

        Returns:
            Absolute snapshot filepath.

        Raises:
            SnapshotSaveError: If the frame is missing, OpenCV is unavailable or the write fails.
        """
        return self._write_frame(frame, prefix)

    def save_async(self, frame: object, prefix: str) -> None:
        """Queue one frame for asynchronous persistence.

        Args:
            frame: OpenCV-compatible image buffer.
            prefix: Human-readable filename prefix.

        Returns:
            None.

        Raises:
            SnapshotSaveError: If the frame is missing, OpenCV is unavailable or the async
                queue is already saturated.

        Boundary behavior:
            The async queue is intentionally bounded so snapshot traffic cannot consume
            unbounded memory or stall the perception callback with slow disk writes.
        """
        if frame is None:
            raise SnapshotSaveError('snapshot frame unavailable')
        if cv2 is None:
            raise SnapshotSaveError('opencv unavailable for snapshot save')
        cloned = self._clone_frame(frame)
        try:
            self._request_queue.put_nowait((cloned, prefix))
        except Full as exc:
            raise SnapshotSaveError('snapshot queue full') from exc

    def poll_results(self, *, max_items: int = 8) -> list[SnapshotResult]:
        """Drain completed async snapshot results without blocking.

        Args:
            max_items: Maximum number of result items to return.

        Returns:
            Completed async snapshot results.

        Raises:
            None.
        """
        results: list[SnapshotResult] = []
        limit = max(1, int(max_items))
        while len(results) < limit:
            try:
                item = self._result_queue.get_nowait()
            except Empty:
                break
            results.append(item)
        return results

    def queue_depth(self) -> int:
        return int(self._request_queue.qsize())

    def close(self) -> None:
        """Stop the async worker and release background resources.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            Shutdown must not depend on queue capacity. Even when the async request queue is
            full, the worker must observe the stop signal and exit without leaking a background
            thread into later tests or runtime teardown.
        """
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        while True:
            try:
                self._request_queue.put_nowait(None)
                break
            except Full:
                try:
                    self._request_queue.get_nowait()
                except Empty:
                    break
        if self._worker.is_alive():
            self._worker.join(timeout=2.0)

    def _worker_main(self) -> None:
        while True:
            if self._stop_event.is_set() and self._request_queue.empty():
                return
            try:
                item = self._request_queue.get(timeout=0.1)
            except Empty:
                continue
            if item is None:
                return
            frame, prefix = item
            try:
                path = self._write_frame(frame, prefix)
            except SnapshotSaveError as exc:
                self._result_queue.put(SnapshotResult(success=False, error=str(exc), prefix=str(prefix)))
            else:
                self._result_queue.put(SnapshotResult(success=True, filepath=path, prefix=str(prefix)))

    def _write_frame(self, frame: object, prefix: str) -> str:
        if frame is None:
            raise SnapshotSaveError('snapshot frame unavailable')
        if cv2 is None:
            raise SnapshotSaveError('opencv unavailable for snapshot save')
        filename = f'{slugify(prefix)}_{int(time.time() * 1000)}.jpg'
        path = self.output_dir / filename
        ok = bool(cv2.imwrite(str(path), frame))
        if not ok or not path.exists():
            raise SnapshotSaveError(f'snapshot write failed: {path}')
        return str(path)

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
