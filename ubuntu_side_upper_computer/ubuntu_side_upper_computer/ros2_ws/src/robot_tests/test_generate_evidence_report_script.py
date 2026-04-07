from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_generate_evidence_report_script_with_explicit_paths(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'generate_evidence_report.py'
    metrics = tmp_path / 'metrics.json'
    evidence = tmp_path / 'evidence_index.json'
    output = tmp_path / 'report.json'
    metrics.write_text(json.dumps({'reconnect_count': 1, 'events_logged': 3}), encoding='utf-8')
    evidence.write_text(json.dumps({'health': 'good', 'recent_events': ['evt-1']}), encoding='utf-8')
    subprocess.run(
        [sys.executable, str(script), '--metrics', str(metrics), '--evidence', str(evidence), '--output', str(output)],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(repo_root),
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['health'] == 'good'
    assert payload['events_logged'] == 3
