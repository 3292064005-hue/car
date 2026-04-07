from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

from release_gate_manifest import manifest_payload


def test_release_gate_manifest_contains_named_lanes() -> None:
    payload = manifest_payload()
    lane_titles = {lane['title'] for lane in payload['lanes']}
    assert {'Frontend E2E', 'Mock system web bridge launch smoke', 'Integrated frontend + web bridge smoke'} <= lane_titles


def test_release_gate_consistency_script_passes_for_repo_snapshot() -> None:
    repo_root = REPO_ROOT
    script = repo_root / 'scripts' / 'check_release_gate_consistency.py'
    subprocess.run([sys.executable, str(script)], cwd=str(repo_root), check=True)
