from pathlib import Path

import pytest

from robot_vision import snapshot_manager as snapshot_manager_module
from robot_vision.snapshot_manager import SnapshotManager, SnapshotSaveError


class _FakeCv2:
    def __init__(self, succeed: bool, create_file: bool) -> None:
        self.succeed = succeed
        self.create_file = create_file

    def imwrite(self, path: str, frame) -> bool:
        if self.create_file:
            Path(path).write_bytes(b'jpeg')
        return self.succeed


def test_save_raises_when_frame_missing(tmp_path) -> None:
    manager = SnapshotManager(str(tmp_path))
    with pytest.raises(SnapshotSaveError):
        manager.save(None, 'manual')


def test_save_raises_when_write_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(snapshot_manager_module, 'cv2', _FakeCv2(succeed=False, create_file=False))
    manager = SnapshotManager(str(tmp_path))
    with pytest.raises(SnapshotSaveError):
        manager.save(object(), 'manual')


def test_save_returns_existing_path_on_success(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(snapshot_manager_module, 'cv2', _FakeCv2(succeed=True, create_file=True))
    manager = SnapshotManager(str(tmp_path))
    path = manager.save(object(), 'manual')
    assert Path(path).exists()


def test_save_async_emits_result_without_blocking(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(snapshot_manager_module, 'cv2', _FakeCv2(succeed=True, create_file=True))
    manager = SnapshotManager(str(tmp_path), async_queue_max=2)
    manager.save_async(object(), 'queued')
    for _ in range(20):
        results = manager.poll_results(max_items=2)
        if results:
            assert results[0].success is True
            assert Path(results[0].filepath).exists()
            break
        import time
        time.sleep(0.01)
    else:
        raise AssertionError('async snapshot result not observed')
    manager.close()


def test_save_async_rejects_when_queue_is_full(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(snapshot_manager_module, 'cv2', _FakeCv2(succeed=True, create_file=True))
    manager = SnapshotManager(str(tmp_path), async_queue_max=1)
    manager.save_async(object(), 'first')
    with pytest.raises(SnapshotSaveError):
        manager.save_async(object(), 'second')
    manager.close()


def test_close_stops_worker_even_when_queue_is_full(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(snapshot_manager_module, 'cv2', _FakeCv2(succeed=True, create_file=True))
    manager = SnapshotManager(str(tmp_path), async_queue_max=1)
    manager.save_async(object(), 'first')
    manager.close()
    assert manager._worker.is_alive() is False
