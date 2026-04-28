from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'check_embedded_host_builds.py'
ROOT = Path(__file__).resolve().parents[3]


def test_embedded_host_build_script_runs() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload['esp32']['lines'] >= 1
    assert payload['stm32']['lines'] >= 1
    assert payload['embedded_mirror_validation']['status'] == 'ok'
    assert any(line.startswith('gateway boundary ') for line in payload['esp32']['sample'])
    assert any(line.startswith('gateway_config_source=') for line in payload['esp32']['sample'])
    assert any(line.startswith('chassis boundary ') for line in payload['stm32']['sample'])
    assert any(line.startswith('harness_config ') for line in payload['stm32']['sample'])
    assert payload['esp32']['source_root'] == str(ROOT / 'esp32s3_code' / 'esp32_s3_gateway')
    assert payload['stm32']['source_root'] == str(ROOT / 'stm32_code' / 'stm32_f103_chassis')


def test_embedded_runtime_core_files_exist() -> None:
    assert (ROOT / 'esp32s3_code' / 'esp32_s3_gateway' / 'main' / 'gateway_runtime.c').exists()
    assert (ROOT / 'esp32s3_code' / 'esp32_s3_gateway' / 'main' / 'gateway_runtime.h').exists()
    assert (ROOT / 'esp32s3_code' / 'esp32_s3_gateway' / 'main' / 'gateway_runtime_config_loader.c').exists()
    assert (ROOT / 'stm32_code' / 'stm32_f103_chassis' / 'Src' / 'chassis_runtime.c').exists()
    assert (ROOT / 'stm32_code' / 'stm32_f103_chassis' / 'Inc' / 'chassis_runtime.h').exists()
    assert (ROOT / 'stm32_code' / 'stm32_f103_chassis' / 'Src' / 'host_harness_config.c').exists()
