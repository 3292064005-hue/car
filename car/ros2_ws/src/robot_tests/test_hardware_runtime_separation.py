from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_hardware_runtime_separation_gate_passes() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'check_hardware_runtime_separation.py')],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload['status'] == 'ok'
    assert payload['separationMode'] == 'dedicated_modules_with_thin_wrappers'


def test_embedded_wrappers_delegate_to_dedicated_modules() -> None:
    esp_wrapper = (ROOT / 'esp32s3_code' / 'esp32_s3_gateway' / 'src' / 'app_main.c').read_text(encoding='utf-8')
    stm_wrapper = (ROOT / 'stm32_code' / 'stm32_f103_chassis' / 'src' / 'main.c').read_text(encoding='utf-8')
    assert 'gateway_host_harness_main()' in esp_wrapper
    assert 'gateway_print_runtime_boundary(gateway_board_runtime_boundary())' in esp_wrapper
    assert 'gateway_runtime_load_default' not in esp_wrapper
    assert 'chassis_host_harness_main()' in stm_wrapper
    assert 'chassis_print_runtime_boundary(chassis_board_runtime_boundary())' in stm_wrapper
    assert 'host_harness_config_apply' not in stm_wrapper
