from __future__ import annotations

"""Low-level MJPEG runtime helpers."""

import multiprocessing as mp
import time
from queue import Empty, Full
from typing import Any

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


def replace_queue_item(queue_obj: Any, item: object) -> None:
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


def capture_process_main(stream_url: str, reconnect_backoff_sec: float, reopen_after_misses: int, frame_queue: Any, stats_queue: Any, stop_event: Any) -> None:
    cap = None
    successful_opens = 0
    reconnect_count = 0
    read_failures = 0
    miss_streak = 0
    connected = False
    last_error = 'capture worker not started'
    latest_stamp = 0.0

    def publish_stats() -> None:
        replace_queue_item(stats_queue, {
            'connected': connected,
            'reconnectCount': reconnect_count,
            'readFailures': read_failures,
            'lastError': last_error,
            'missStreak': miss_streak,
            'frameStamp': latest_stamp,
        })

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
        replace_queue_item(frame_queue, {'frame': frame, 'stamp': latest_stamp})
        publish_stats()
        time.sleep(0.001)

    connected = False
    publish_stats()
    release_cap()


def resolve_process_context() -> Any | None:
    try:
        methods = mp.get_all_start_methods()
    except Exception:
        return None
    if 'fork' in methods:
        return mp.get_context('fork')
    return None


def drain_latest_packet(queue_obj: Any) -> object | None:
    latest_packet = None
    if queue_obj is None:
        return None
    while True:
        try:
            latest_packet = queue_obj.get_nowait()
        except Empty:
            break
        except Exception:
            break
    return latest_packet


def close_ipc_handle(queue_obj: Any) -> None:
    if queue_obj is None:
        return
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


def clone_frame(frame: object | None) -> object | None:
    if frame is None:
        return None
    copy_method = getattr(frame, 'copy', None)
    if callable(copy_method):
        try:
            return copy_method()
        except Exception:
            return frame
    return frame
