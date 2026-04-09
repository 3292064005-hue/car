from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path



def test_embedded_source_sync_script_passes_for_repo_snapshot() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'check_embedded_source_sync.py'
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, cwd=str(repo_root), check=True)
    payload = json.loads(result.stdout)
    assert payload['status'] == 'ok'
    assert payload['canonicalPairCount'] >= 1
    assert payload['checkedMirrorCount'] >= payload['canonicalPairCount']
