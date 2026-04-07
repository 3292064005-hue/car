import json
from pathlib import Path

from robot_monitor.evidence_report import build_evidence_report


def test_build_evidence_report_summarizes_inputs(tmp_path: Path):
    metrics = tmp_path / 'metrics.json'
    evidence = tmp_path / 'evidence_index.json'
    metrics.write_text(json.dumps({'reconnect_count': 2, 'protocol_errors': 1, 'events_logged': 5, 'summaries_published': 3}), encoding='utf-8')
    evidence.write_text(json.dumps({'health': 'degraded', 'last_fault': 'LOW_BAT:warn', 'recent_snapshots': ['a.jpg'], 'recent_events': ['x'], 'last_protocol_issue': 'bad_proto'}), encoding='utf-8')
    report = build_evidence_report(metrics_path=metrics, evidence_index_path=evidence)
    assert report['status'] == 'ready_for_review'
    assert report['snapshot_count'] == 1
    assert report['protocol_errors'] == 1
