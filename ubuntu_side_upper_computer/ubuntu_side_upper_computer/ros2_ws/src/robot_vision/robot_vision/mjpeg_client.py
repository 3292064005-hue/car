from __future__ import annotations

import multiprocessing as mp
from queue import Empty, Full
import threading
import time
from typing import Any

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None



def _replace_queue_item(queue_obj: Any, item: object) -> None:
    """Best-effort latest-value queue publish helper.

    Args:
        queue_obj: Queue-like object exposing ``put_nowait`` / ``get_nowait``.
        item: Item to publish.

    Returns:
        None.

    Raises:
        None. Queue saturation is treated as latest-value replacement rather than a hard error.
    """
    try:
        queue_obj.put_nowait(item)
        return
    except Full:
        pass
    try:
        queue_obj.get_nowait()
    except Empty:
        pass
    except Exception:
        pass
    try:
        queue_obj.put_nowait(item)
    except Full:
        pass



def _capture_process_main(
    stream_url: str,
    reconnect_backoff_sec: float,
    reopen_after_misses: int,
    frame_queue: Any,
    stats_queue: Any,
    stop_event: Any,
) -> None:
    """Run MJPEG capture in a dedicated process and publish latest frames/stats.

    Args:
        stream_url: MJPEG endpoint.
        reconnect_backoff_sec: Backoff between reconnect attempts.
        reopen_after_misses: Consecutive read misses before forcing reopen.
        frame_queue: Latest-frame IPC queue.
        stats_queue: Capture health IPC queue.
        stop_event: Cross-process shutdown signal.

    Returns:
        None.

    Raises:
        None. Worker failures are reflected through stats packets.
    """
    cap = None
    successful_opens = 0
    reconnect_count = 0
    read_failures = 0
    miss_streak = 0
    connected = False
    last_error = 'capture worker not started'
    latest_stamp = 0.0

    def publish_stats() -> None:
        _replace_queue_item(
            stats_queue,
            {
                'connected': connected,
                'reconnectCount': reconnect_count,
                'readFailures': read_failures,
                'lastError': last_error,
                'missStreak': miss_streak,
                'frameStamp': latest_stamp,
            },
        )

    def release_cap() -> None:
        nonlocal cap
        if cap is None:
            return
        try:
            cap.release()
        except Exception:
            pass
        cap = None

    last_error = ''
    publish_stats()
    while not stop_event.is_set():
        if cap is None or not getattr(cap, 'isOpened', lambda: False)():
            if cv2 is None:
                connected = False
                last_error = 'opencv unavailable'
                publish_stats()
                time.sleep(reconnect_backoff_sec)
                continue
            cap = cv2.VideoCapture(stream_url)
            if not cap or not cap.isOpened():
                connected = False
                last_error = f'failed to open stream: {stream_url}'
                publish_stats()
                release_cap()
                time.sleep(reconnect_backoff_sec)
                continue
            if successful_opens > 0:
                reconnect_count += 1
            successful_opens += 1
            connected = True
            miss_streak = 0
            last_error = ''
            publish_stats()

        ok, frame = cap.read()
        if not ok or frame is None:
            read_failures += 1
            miss_streak += 1
            last_error = 'stream read failed'
            publish_stats()
            if miss_streak >= reopen_after_misses:
                connected = False
                publish_stats()
                release_cap()
                time.sleep(reconnect_backoff_sec)
            else:
                time.sleep(0.02)
            continue

        latest_stamp = time.monotonic()
        connected = True
        miss_streak = 0
        last_error = ''
        _replace_queue_item(frame_queue, {'frame': frame, 'stamp': latest_stamp})
        publish_stats()
        time.sleep(0.001)

    connected = False
    publish_stats()
    release_cap()


class MjpegClient:
    """Latest-frame MJPEG capture client with reconnect handling.

    The client supports two execution modes:
    1. Thread mode keeps capture in-process for simple unit tests and environments where
       process isolation is unavailable.
    2. Process mode isolates stream I/O in a dedicated child process so slow or unstable
       capture cannot directly stall the ROS executor thread pool.
    """

    def __init__(
        self,
        stream_url: str,
        *,
        reconnect_backoff_sec: float = 0.5,
        reopen_after_misses: int = 5,
        use_capture_process: bool = False,
        ipc_queue_max: int = 1,
    ) -> None:
        self.stream_url = stream_url
        self.reconnect_backoff_sec = max(0.05, float(reconnect_backoff_sec))
        self.reopen_after_misses = max(1, int(reopen_after_misses))
        self.use_capture_process = bool(use_capture_process)
        self.ipc_queue_max = max(1, int(ipc_queue_max))
        self._lock = threading.RLock()
        self._cap: Any | None = None
        self._thread: threading.Thread | None = None
        self._process: Any | None = None
        self._process_ctx = self._resolve_process_context() if self.use_capture_process else None
        self._process_stop_event: Any | None = None
        self._frame_queue: Any | None = None
        self._stats_queue: Any | None = None
        self._stop_event = threading.Event()
        self._latest_frame: object | None = None
        self._latest_stamp = 0.0
        self._connected = False
        self._successful_opens = 0
        self._reconnect_count = 0
        self._read_failures = 0
        self._last_error = ''
        self._miss_streak = 0
        self._capture_mode = 'process' if self.use_capture_process and self._process_ctx is not None else 'thread'

    def open(self) -> bool:
        """Start the background capture worker.

        Args:
            None.

        Returns:
            ``True`` when the worker is started or already running, else ``False`` when
            OpenCV is unavailable.

        Raises:
            None.
        """
        if cv2 is None:
            self._last_error = 'opencv unavailable'
            return False
        if self.use_capture_process and self._process_ctx is not None:
            return self._open_process_worker()
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()
            self._capture_mode = 'thread'
            return True

    def read(self) -> tuple[bool, object | None]:
        """Read the latest available frame snapshot.

        Args:
            None.

        Returns:
            ``(True, frame)`` when a frame is available, else ``(False, None)``.

        Raises:
            None.
        """
        self._refresh_from_ipc()
        with self._lock:
            if self._latest_frame is None:
                return False, None
            return True, self._clone_frame(self._latest_frame)

    def close(self) -> None:
        """Stop capture and release the underlying capture resources.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.

        Boundary behavior:
            The close path first signals the active worker, then waits with bounded
            timeouts and finally force-terminates a stuck process worker so shutdown
            cannot leak capture resources into later tests or node teardown.
        """
        self._stop_event.set()
        thread = None
        process = None
        stop_event = None
        with self._lock:
            thread = self._thread
            process = self._process
            stop_event = self._process_stop_event
        if stop_event is not None:
            stop_event.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        if process is not None and process.is_alive():
            process.join(timeout=2.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
        self._close_ipc_handles()
        with self._lock:
            self._release_locked()
            self._thread = None
            self._process = None
            self._process_stop_event = None
            self._connected = False
            self._latest_frame = None
            self._latest_stamp = 0.0
            self._miss_streak = 0
            self._capture_mode = 'process' if self.use_capture_process and self._process_ctx is not None else 'thread'

    def stats(self) -> dict[str, Any]:
        """Return a snapshot of capture health metrics for diagnostics."""
        self._refresh_from_ipc()
        with self._lock:
            now = time.monotonic()
            frame_age_ms = max(0.0, (now - self._latest_stamp) * 1000.0) if self._latest_stamp > 0.0 else 0.0
            return {
                'connected': self._connected,
                'reconnectCount': self._reconnect_count,
                'readFailures': self._read_failures,
                'lastError': self._last_error,
                'missStreak': self._miss_streak,
                'frameAgeMs': round(frame_age_ms, 3),
                'captureMode': self._capture_mode,
            }

    def _open_process_worker(self) -> bool:
        with self._lock:
            if self._process is not None and self._process.is_alive():
                return True
            ctx = self._process_ctx
            if ctx is None:
                return False
            self._latest_frame = None
            self._latest_stamp = 0.0
            self._frame_queue = ctx.Queue(maxsize=self.ipc_queue_max)
            self._stats_queue = ctx.Queue(maxsize=max(2, self.ipc_queue_max * 2))
            self._process_stop_event = ctx.Event()
            self._process = ctx.Process(
                target=_capture_process_main,
                args=(
                    self.stream_url,
                    self.reconnect_backoff_sec,
                    self.reopen_after_misses,
                    self._frame_queue,
                    self._stats_queue,
                    self._process_stop_event,
                ),
                daemon=True,
            )
            self._process.start()
            self._capture_mode = 'process'
            return True

    def _refresh_from_ipc(self) -> None:
        frame_packet = None
        stats_packet = None
        frame_queue = None
        stats_queue = None
        process = None
        with self._lock:
            frame_queue = self._frame_queue
            stats_queue = self._stats_queue
            process = self._process
        if frame_queue is not None:
            while True:
                try:
                    frame_packet = frame_queue.get_nowait()
                except Empty:
                    break
                except Exception:
                    break
        if stats_queue is not None:
            while True:
                try:
                    stats_packet = stats_queue.get_nowait()
                except Empty:
                    break
                except Exception:
                    break
        with self._lock:
            if frame_packet is not None:
                self._latest_frame = frame_packet.get('frame')
                self._latest_stamp = float(frame_packet.get('stamp', 0.0) or 0.0)
            if stats_packet is not None:
                self._connected = bool(stats_packet.get('connected', False))
                self._reconnect_count = int(stats_packet.get('reconnectCount', 0) or 0)
                self._read_failures = int(stats_packet.get('readFailures', 0) or 0)
                self._last_error = str(stats_packet.get('lastError', '') or '')
                self._miss_streak = int(stats_packet.get('missStreak', 0) or 0)
                stamp = float(stats_packet.get('frameStamp', 0.0) or 0.0)
                if stamp > self._latest_stamp:
                    self._latest_stamp = stamp
            if process is not None and not process.is_alive() and self._process_stop_event is not None and not self._process_stop_event.is_set():
                self._connected = False
                if not self._last_error:
                    self._last_error = 'capture worker exited unexpectedly'

    def _close_ipc_handles(self) -> None:
        for attr in ('_frame_queue', '_stats_queue'):
            queue_obj = getattr(self, attr)
            if queue_obj is None:
                continue
            close = getattr(queue_obj, 'close', None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
            join_thread = getattr(queue_obj, 'join_thread', None)
            if callable(join_thread):
                try:
                    join_thread()
                except Exception:
                    pass
            setattr(self, attr, None)

    def _capture_loop(self) -> None:
        while not self._stop_event.is_set():
            if not self._ensure_connected():
                time.sleep(self.reconnect_backoff_sec)
                continue
            cap = None
            with self._lock:
                cap = self._cap
            if cap is None:
                time.sleep(self.reconnect_backoff_sec)
                continue
            ok, frame = cap.read()
            if not ok or frame is None:
                with self._lock:
                    self._read_failures += 1
                    self._miss_streak += 1
                    self._last_error = 'stream read failed'
                    should_reopen = self._miss_streak >= self.reopen_after_misses
                    if should_reopen:
                        self._connected = False
                        self._release_locked()
                if should_reopen:
                    time.sleep(self.reconnect_backoff_sec)
                else:
                    time.sleep(0.02)
                continue
            with self._lock:
                self._latest_frame = frame
                self._latest_stamp = time.monotonic()
                self._miss_streak = 0
                self._last_error = ''
            time.sleep(0.001)

    def _ensure_connected(self) -> bool:
        with self._lock:
            if self._cap is not None and getattr(self._cap, 'isOpened', lambda: False)():
                self._connected = True
                return True
        if cv2 is None:
            with self._lock:
                self._last_error = 'opencv unavailable'
            return False
        cap = cv2.VideoCapture(self.stream_url)
        if not cap or not cap.isOpened():
            with self._lock:
                self._connected = False
                self._last_error = f'failed to open stream: {self.stream_url}'
                try:
                    cap.release()
                except Exception:
                    pass
            return False
        with self._lock:
            if self._successful_opens > 0:
                self._reconnect_count += 1
            self._successful_opens += 1
            self._cap = cap
            self._connected = True
            self._miss_streak = 0
            self._last_error = ''
        return True

    def _release_locked(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    @staticmethod
    def _resolve_process_context() -> Any | None:
        try:
            methods = mp.get_all_start_methods()
        except Exception:
            return None
        if 'fork' in methods:
            return mp.get_context('fork')
        return None

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
