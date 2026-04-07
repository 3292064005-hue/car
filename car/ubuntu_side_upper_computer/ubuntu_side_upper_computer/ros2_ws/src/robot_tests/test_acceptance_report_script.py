from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _prepare_paths(tmp_path: Path) -> tuple[Path, Path]:
    metrics = tmp_path / "metrics.json"
    evidence = tmp_path / "evidence_index.json"
    metrics.write_text(json.dumps({"events_logged": 2, "health": "ok", "recent_event_count": 1}), encoding="utf-8")
    evidence.write_text(json.dumps({"snapshot_count": 1, "recent_snapshots": ["snap-1"], "status": "ready_for_review", "health": "good", "readiness": "ready"}), encoding="utf-8")
    return metrics, evidence


def test_acceptance_report_script_with_defaults(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "render_acceptance_report.py"
    runtime_dir = repo_root / "tmp" / "inspection_robot"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    metrics, evidence = _prepare_paths(runtime_dir)
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True, cwd=str(repo_root))
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_review"
    assert payload["acceptanceGate"] == "pass"
    assert Path(metrics).exists()
    assert Path(evidence).exists()


def test_acceptance_report_script_with_explicit_paths(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "render_acceptance_report.py"
    metrics, evidence = _prepare_paths(tmp_path)
    result = subprocess.run(
        [sys.executable, str(script), "--metrics", str(metrics), "--evidence", str(evidence)],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(repo_root),
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_review"
    assert payload["acceptanceGate"] == "pass"
