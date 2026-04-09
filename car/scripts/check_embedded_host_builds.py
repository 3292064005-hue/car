#!/usr/bin/env python3
from __future__ import annotations

"""Build and execute host-side harness demos for the split embedded projects."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from embedded_source_sync import validate_embedded_mirrors
from workspace_layout import resolve_workspace_layout

LAYOUT = resolve_workspace_layout(Path(__file__))
ESP_ROOT = LAYOUT.canonical_esp_root
STM_ROOT = LAYOUT.canonical_stm_root


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run one command and capture its completed-process payload."""
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=True)


def _gcc() -> str:
    """Resolve the host GCC executable required for harness builds."""
    gcc = shutil.which('gcc')
    if not gcc:
        raise RuntimeError('gcc not found in PATH')
    return gcc


def _require_directory(path: Path, *, label: str) -> Path:
    """Return one required source directory after existence validation.

    Args:
        path: Candidate directory.
        label: Human-readable source label used in failure messages.

    Returns:
        Existing directory path.

    Raises:
        RuntimeError: When the split snapshot does not contain the requested
            embedded source root.

    Boundary behavior:
        The script aborts before invoking GCC so packaging drift is reported as
        a deterministic layout error instead of a subprocess failure.
    """
    if not path.is_dir():
        raise RuntimeError(f'missing required {label}: {path}')
    return path


def _collect_c_sources(root: Path, *, label: str) -> list[Path]:
    """Collect one non-empty C source list from a validated source root.

    Args:
        root: Source root that contains ``src`` and ``include`` children.
        label: Human-readable runtime label.

    Returns:
        Sorted list of ``.c`` files.

    Raises:
        RuntimeError: When the expected ``src`` or ``include`` directories are
            missing, or when no host-harness C sources are present.
    """
    include_dir = _require_directory(root / 'include', label=f'{label} include directory')
    del include_dir
    src_dir = _require_directory(root / 'src', label=f'{label} source directory')
    sources = sorted(src_dir.glob('*.c'))
    if not sources:
        raise RuntimeError(f'{label} host harness has no C sources under {src_dir}')
    return sources


def build_esp_host(tmp: Path) -> dict[str, object]:
    """Build and run the ESP32 gateway host harness.

    Args:
        tmp: Temporary directory that will hold the compiled binary.

    Returns:
        Serializable report payload for the harness run.

    Raises:
        RuntimeError: If compilation or execution does not produce a usable demo.
    """
    gcc = _gcc()
    esp_root = _require_directory(ESP_ROOT, label='ESP32 source root')
    esp_sources = _collect_c_sources(esp_root, label='ESP32 gateway')
    exe = tmp / 'esp32_gateway_demo'
    cmd = [gcc, '-std=c11', '-Wall', '-Wextra', '-pedantic', '-I', str(esp_root / 'include')]
    cmd.extend(str(path) for path in esp_sources)
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
        'source_root': str(esp_root),
    }


def build_stm_host(tmp: Path) -> dict[str, object]:
    """Build and run the STM32 chassis host harness.

    Args:
        tmp: Temporary directory that will hold the compiled binary.

    Returns:
        Serializable report payload for the harness run.

    Raises:
        RuntimeError: If compilation or execution does not produce a usable demo.
    """
    gcc = _gcc()
    stm_root = _require_directory(STM_ROOT, label='STM32 source root')
    stm_sources = _collect_c_sources(stm_root, label='STM32 chassis')
    exe = tmp / 'stm32_chassis_demo'
    cmd = [gcc, '-std=c11', '-Wall', '-Wextra', '-pedantic', '-I', str(stm_root / 'include')]
    cmd.extend(str(path) for path in stm_sources)
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
        'source_root': str(stm_root),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='embedded-host-builds-') as tmpdir:
        tmp = Path(tmpdir)
        report = {
            'overall_scope': 'host_harness_only',
            'embedded_mirror_validation': validate_embedded_mirrors(),
            'layout': {
                'canonical_root': str(LAYOUT.ubuntu_root),
                'outer_root': str(LAYOUT.repo_root),
                'compatibility_ubuntu_root': str(LAYOUT.compatibility_ubuntu_root),
                'esp_root': str(ESP_ROOT),
                'stm_root': str(STM_ROOT),
            },
            'esp32': build_esp_host(tmp),
            'stm32': build_stm_host(tmp),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
