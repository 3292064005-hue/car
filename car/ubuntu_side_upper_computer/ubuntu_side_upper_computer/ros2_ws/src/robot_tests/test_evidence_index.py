import json
from pathlib import Path

from robot_monitor.event_logger import EvidenceIndex, JsonlEventLogger


def test_evidence_index_tracks_recent_events_and_snapshots(tmp_path: Path):
    path = tmp_path / 'evidence.json'
    idx = EvidenceIndex(str(path), max_recent=2)
    idx.record_event('bridge', 'connected', 'ok')
    idx.record_event('vision', 'snapshot_saved', '/tmp/a.jpg')
    idx.record_snapshot('/tmp/a.jpg')
    idx.record_event('fault', 'LOW_BAT', 'warn')
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['last_snapshot'] == '/tmp/a.jpg'
    assert len(data['recent_events']) == 2
    assert data['recent_snapshots'] == ['/tmp/a.jpg']


def test_evidence_index_flush_is_atomic(tmp_path: Path):
    path = tmp_path / 'evidence.json'
    idx = EvidenceIndex(str(path), max_recent=2)
    idx.update(health='good')
    assert json.loads(path.read_text(encoding='utf-8'))['health'] == 'good'


def test_jsonl_event_logger_rotates_files(tmp_path: Path):
    path = tmp_path / 'events.jsonl'
    logger = JsonlEventLogger(str(path), auto_flush_every=1, rotate_max_bytes=40, backup_count=2)
    logger.append({'event': 'one', 'blob': 'x' * 40})
    logger.append({'event': 'two', 'blob': 'x' * 40})
    logger.flush()
    assert path.exists()
    assert path.with_suffix('.jsonl.1').exists()
