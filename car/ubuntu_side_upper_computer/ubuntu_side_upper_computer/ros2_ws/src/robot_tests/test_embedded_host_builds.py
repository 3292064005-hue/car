from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'check_embedded_host_builds.py'
ROOT = Path(__file__).resolve().parents[4]


def test_embedded_host_build_script_runs() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload['esp32']['lines'] >= 1
    assert payload['stm32']['lines'] >= 1
    assert payload['esp32']['sample'][0].startswith('gateway_config_source=')
    assert payload['stm32']['sample'][0].startswith('harness_config ')


def test_embedded_runtime_core_files_exist() -> None:
    assert (ROOT / 'esp32s3_code' / 'esp32_s3_gateway' / 'main' / 'gateway_runtime.c').exists()
    assert (ROOT / 'esp32s3_code' / 'esp32_s3_gateway' / 'main' / 'gateway_runtime.h').exists()
    assert (ROOT / 'esp32s3_code' / 'esp32_s3_gateway' / 'main' / 'gateway_runtime_config_loader.c').exists()
    assert (ROOT / 'stm32_code' / 'stm32_f103_chassis' / 'Src' / 'chassis_runtime.c').exists()
    assert (ROOT / 'stm32_code' / 'stm32_f103_chassis' / 'Inc' / 'chassis_runtime.h').exists()
    assert (ROOT / 'stm32_code' / 'stm32_f103_chassis' / 'Src' / 'host_harness_config.c').exists()
