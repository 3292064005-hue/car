import os
import time

import pytest

from robot_vision import mjpeg_client as mjpeg_client_module
from robot_vision.mjpeg_client import MjpegClient


class _FakeCap:
    def __init__(self, frames) -> None:
        self._frames = list(frames)
        self._opened = True

    def isOpened(self) -> bool:
        return self._opened

    def read(self):
        if self._frames:
            return True, self._frames.pop(0)
        return False, None

    def release(self) -> None:
        self._opened = False


class _FakeCv2:
    def __init__(self, frames) -> None:
        self._frames = frames

    def VideoCapture(self, stream_url: str):
        return _FakeCap(self._frames)



def test_close_clears_latest_frame_state() -> None:
    client = MjpegClient('http://example/stream')
    client._latest_frame = object()
    client._latest_stamp = 123.0
    client._connected = True

    client.close()

    ok, frame = client.read()
    assert ok is False
    assert frame is None
    assert client.stats()['connected'] is False


@pytest.mark.filterwarnings(r'ignore:This process .* is multi-threaded, use of fork\(\) may lead to deadlocks in the child\.:DeprecationWarning')
@pytest.mark.skipif('fork' not in mjpeg_client_module.mp.get_all_start_methods(), reason='capture process requires fork context')
def test_process_mode_reads_latest_frame(monkeypatch) -> None:
    monkeypatch.setattr(mjpeg_client_module, 'cv2', _FakeCv2(frames=[{'seq': 1}, {'seq': 2}]))
    client = MjpegClient('http://example/stream', use_capture_process=True, ipc_queue_max=1)
    assert client.open() is True
    for _ in range(50):
        ok, frame = client.read()
        if ok:
            assert frame in ({'seq': 1}, {'seq': 2})
            break
        time.sleep(0.02)
    else:
        raise AssertionError('process capture frame not observed')
    stats = client.stats()
    assert stats['captureMode'] == 'process'
    client.close()
    assert client.stats()['connected'] is False
