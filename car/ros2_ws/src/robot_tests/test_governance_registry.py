from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from robot_contracts.lane_registry import lane_registry_payload
from robot_contracts.signal_ownership import governance_signal_registry_payload, validate_signal_registry

ROOT = Path(__file__).resolve().parents[3]


def test_signal_registry_validation_has_no_errors() -> None:
    assert validate_signal_registry() == []
    payload = governance_signal_registry_payload()
    assert payload['validationErrors'] == []
    assert 'apply_param_draft' in payload['commands']
    assert payload['runtimeParameters']['maxLinearSpeed']['ackOwners'] == ['robot_control', 'robot_decision']


def test_lane_registry_contains_navigation_and_hardware_experimental_lanes() -> None:
    payload = lane_registry_payload(include_experimental=True)
    assert payload['navigation.nav2_provider']['packageName'] == 'robot_nav2_adapter'
    assert payload['hardware.direct_driver']['packageName'] == 'robot_direct_driver'
    assert payload['bridge_runtime.legacy_monolith']['activationDecision'] == 'rollback_only'


def test_generate_governance_artifacts_emits_frontend_contract_files(tmp_path: Path) -> None:
    script = ROOT / 'scripts' / 'generate_governance_artifacts.py'
    subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=True)
    json_path = ROOT / 'robot_frontend' / 'src' / 'generated' / 'governanceContract.json'
    ts_path = ROOT / 'robot_frontend' / 'src' / 'generated' / 'governanceContract.ts'
    payload = json.loads(json_path.read_text(encoding='utf-8'))
    assert json_path.is_file()
    assert ts_path.is_file()
    assert payload['laneRegistry']['navigation.nav2_provider']['packageName'] == 'robot_nav2_adapter'
    assert payload['signalRegistry']['validationErrors'] == []
