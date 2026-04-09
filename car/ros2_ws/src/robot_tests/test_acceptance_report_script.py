from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path



def _prepare_paths(tmp_path: Path) -> tuple[Path, Path]:
    metrics = tmp_path / 'metrics.json'
    evidence = tmp_path / 'evidence_index.json'
    metrics.write_text(json.dumps({'events_logged': 2, 'health': 'ok', 'recent_event_count': 1}), encoding='utf-8')
    evidence.write_text(json.dumps({'snapshot_count': 1, 'recent_snapshots': ['snap-1'], 'status': 'ready_for_review', 'health': 'good', 'readiness': 'ready'}), encoding='utf-8')
    return metrics, evidence



def test_acceptance_report_script_with_runtime_dir_default(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'render_acceptance_report.py'
    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    metrics, evidence = _prepare_paths(runtime_dir)
    env = os.environ.copy()
    env['INSPECTION_ROBOT_RUNTIME_DIR'] = str(runtime_dir)
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True, cwd=str(repo_root), env=env)
    payload = json.loads(result.stdout)
    assert payload['status'] == 'ready_for_review'
    assert payload['acceptanceGate'] == 'host_runtime_review_ready'
    assert payload['sourceArtifacts']['runtimeDir'] == str(runtime_dir)
    assert Path(metrics).exists()
    assert Path(evidence).exists()



def test_acceptance_report_script_with_explicit_paths(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'render_acceptance_report.py'
    metrics, evidence = _prepare_paths(tmp_path)
    result = subprocess.run(
        [sys.executable, str(script), '--metrics', str(metrics), '--evidence', str(evidence)],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(repo_root),
    )
    payload = json.loads(result.stdout)
    assert payload['status'] == 'ready_for_review'
    assert payload['acceptanceGate'] == 'host_runtime_review_ready'
    assert payload['inputCoverage'] == 'complete'


def test_acceptance_report_artifact_checklist_includes_monitor_reports(tmp_path):
    from pathlib import Path
    import json, subprocess, sys
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'render_acceptance_report.py'
    output = tmp_path / 'acceptance.json'
    subprocess.run([sys.executable, str(script), '--metrics', str(tmp_path/'missing_metrics.json'), '--evidence', str(tmp_path/'missing_evidence.json'), '--output', str(output)], cwd=str(repo_root), check=True)
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['artifactChecklist']['monitor_summary_report_script'] is True
    assert payload['artifactChecklist']['monitor_diagnostics_report_script'] is True
