from __future__ import annotations

import subprocess
from pathlib import Path


def test_start_backend_requires_config_path_value() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'start_ros2_backend.sh'
    proc = subprocess.run([str(script), 'mock', '--config-path'], cwd=str(repo_root), text=True, capture_output=True)
    assert proc.returncode == 2
    assert 'missing value for --config-path' in proc.stderr


def test_start_backend_requires_preflight_report_dir_value() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'start_ros2_backend.sh'
    proc = subprocess.run([str(script), 'mock', '--preflight-report-dir'], cwd=str(repo_root), text=True, capture_output=True)
    assert proc.returncode == 2
    assert 'missing value for --preflight-report-dir' in proc.stderr
