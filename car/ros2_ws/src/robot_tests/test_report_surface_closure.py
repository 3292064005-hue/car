from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_report_surface_closure_script_passes() -> None:
    completed = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'check_report_surface_closure.py')], cwd=str(ROOT), check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload['status'] == 'ok'
    assert payload['producerKeys'] == payload['contractKeys'] == payload['consumerKeys']
    assert payload['kindDrift'] == {}
    assert payload['detailDrift'] == {}
