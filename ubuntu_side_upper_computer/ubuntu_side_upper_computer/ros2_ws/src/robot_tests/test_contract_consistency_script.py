from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_contract_consistency_script_runs() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'check_contract_consistency.py'
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    assert payload['versions']['web_protocol'] == '4.1.0'
    assert payload['versions']['tcp_transport'] == 1
    assert payload['frontend_protocol'] == '4.1.0'
    assert payload['stm32_uart_protocol_version'] == 1
    assert payload['tcp_doc_has_trace_id'] is True
    assert 'SAFE_STOP' in payload['state_machine_modes']
