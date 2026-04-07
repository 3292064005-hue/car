#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
ESP_ROOT = PROJECT_ROOT / 'esp32s3_code' / 'esp32_s3_gateway'
STM_ROOT = PROJECT_ROOT / 'stm32_code' / 'stm32_f103_chassis'


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=True)


def _gcc() -> str:
    gcc = shutil.which('gcc')
    if not gcc:
        raise RuntimeError('gcc not found in PATH')
    return gcc


def build_esp_host(tmp: Path) -> dict[str, object]:
    gcc = _gcc()
    exe = tmp / 'esp32_gateway_demo'
    cmd = [gcc, '-std=c11', '-Wall', '-Wextra', '-pedantic', '-I', str(ESP_ROOT / 'main')]
    for inc in sorted((ESP_ROOT / 'components').glob('*/include')):
        cmd.extend(['-I', str(inc)])
    cmd.extend(str(path) for path in sorted((ESP_ROOT / 'components').glob('*/*.c')))
    cmd.extend([
        str(ESP_ROOT / 'main' / 'gateway_runtime.c'),
        str(ESP_ROOT / 'main' / 'gateway_runtime_config_loader.c'),
        str(ESP_ROOT / 'main' / 'app_main.c'),
    ])
    cmd.extend(['-o', str(exe)])
    _run(cmd)
    proc = _run([str(exe)])
    out = proc.stdout.strip().splitlines()
    if not out:
        raise RuntimeError('ESP32 host demo produced no output')
    if 'uart_heartbeat_stale' in proc.stdout:
        raise RuntimeError('ESP32 host demo reported uart_heartbeat_stale during early bootstrap')
    return {
        'binary': str(exe),
        'lines': len(out),
        'sample': out[:3],
        'validation_scope': 'host_harness_only',
    }


def build_stm_host(tmp: Path) -> dict[str, object]:
    gcc = _gcc()
    exe = tmp / 'stm32_chassis_demo'
    cmd = [gcc, '-std=c11', '-Wall', '-Wextra', '-pedantic', '-I', str(STM_ROOT / 'Inc')]
    cmd.extend(str(path) for path in sorted((STM_ROOT / 'Src').glob('*.c')))
    cmd.extend(['-o', str(exe)])
    _run(cmd)
    proc = _run([str(exe)])
    out = proc.stdout.strip().splitlines()
    if not out:
        raise RuntimeError('STM32 host demo produced no output')
    if 'pwm L=0.00 R=0.00' not in proc.stdout:
        raise RuntimeError('STM32 host demo did not hard-zero PWM after safety stop')
    return {
        'binary': str(exe),
        'lines': len(out),
        'sample': out[:2],
        'validation_scope': 'host_harness_only',
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='embedded-host-builds-') as tmpdir:
        tmp = Path(tmpdir)
        report = {
            'overall_scope': 'host_harness_only',
            'esp32': build_esp_host(tmp),
            'stm32': build_stm_host(tmp),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
