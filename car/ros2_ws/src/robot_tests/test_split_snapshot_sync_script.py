from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_split_snapshot_sync_reports_single_root_noop() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'check_split_snapshot_sync.py'
    result = subprocess.run(['python3', str(script)], cwd=str(repo_root), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload['status'] == 'ok'
    assert payload['mode'] == 'single_root_noop'
    assert payload['checked_required_path_count'] == 0
    assert payload['checked_wrapper_count'] == 0
