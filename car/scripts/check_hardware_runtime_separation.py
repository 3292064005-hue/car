#!/usr/bin/env python3
from __future__ import annotations

"""Validate physical separation between host-harness shims and board-runtime boundaries."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _require_wrapper(path: Path, *, boundary_call: str, harness_call: str) -> dict[str, object]:
    source = _read(path)
    if boundary_call not in source:
        raise RuntimeError(f'missing board-runtime boundary print in wrapper: {path}')
    if harness_call not in source:
        raise RuntimeError(f'missing host-harness delegation in wrapper: {path}')
    if 'gateway_runtime_load_default' in source or 'host_harness_config_apply' in source:
        raise RuntimeError(f'wrapper still contains harness implementation details instead of delegation: {path}')
    return {
        'path': str(path),
        'boundaryCall': boundary_call,
        'harnessCall': harness_call,
        'wrapperThin': True,
    }


def main() -> int:
    esp = {
        'wrapper': _require_wrapper(
            ROOT / 'esp32s3_code/esp32_s3_gateway/src/app_main.c',
            boundary_call='gateway_print_runtime_boundary(gateway_board_runtime_boundary())',
            harness_call='gateway_host_harness_main()',
        ),
        'hostHarnessModule': str(ROOT / 'esp32s3_code/esp32_s3_gateway/src/host_harness_entry.c'),
        'boardBoundaryModule': str(ROOT / 'esp32s3_code/esp32_s3_gateway/src/board_runtime_boundary.c'),
    }
    stm = {
        'wrapper': _require_wrapper(
            ROOT / 'stm32_code/stm32_f103_chassis/src/main.c',
            boundary_call='chassis_print_runtime_boundary(chassis_board_runtime_boundary())',
            harness_call='chassis_host_harness_main()',
        ),
        'hostHarnessModule': str(ROOT / 'stm32_code/stm32_f103_chassis/src/host_harness_entry.c'),
        'boardBoundaryModule': str(ROOT / 'stm32_code/stm32_f103_chassis/src/board_runtime_boundary.c'),
    }
    for path_str in (esp['hostHarnessModule'], esp['boardBoundaryModule'], stm['hostHarnessModule'], stm['boardBoundaryModule']):
        path = Path(path_str)
        if not path.is_file():
            raise RuntimeError(f'missing required separation module: {path}')
    payload = {
        'status': 'ok',
        'separationMode': 'dedicated_modules_with_thin_wrappers',
        'esp32': esp,
        'stm32': stm,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
