from __future__ import annotations

import json
import os
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
    assert payload['sourceArtifacts']['metrics']['exists'] is True
    assert payload['inputCoverage'] == 'complete'
    assert payload['finalDeliveryEligible'] is False



def test_generate_evidence_report_runtime_dir_defaults_to_env(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'generate_evidence_report.py'
    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir()
    (runtime_dir / 'metrics.json').write_text(json.dumps({'events_logged': 5}), encoding='utf-8')
    (runtime_dir / 'evidence_index.json').write_text(json.dumps({'health': 'good'}), encoding='utf-8')
    env = os.environ.copy()
    env['INSPECTION_ROBOT_RUNTIME_DIR'] = str(runtime_dir)
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True, cwd=str(repo_root), env=env)
    payload = json.loads(result.stdout)
    assert payload['sourceArtifacts']['runtimeDir'] == str(runtime_dir)
    assert payload['status'] == 'ready_for_review'
    assert payload['reviewGate'] == 'host_runtime_review_ready'
