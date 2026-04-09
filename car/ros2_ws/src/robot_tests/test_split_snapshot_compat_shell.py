from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_single_root_entrypoints_dispatch_in_place() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    for script_name in ('start_frontend.sh', 'start_ros2_backend.sh', 'start_web_bridge.sh', 'scripts/run_release_verification.sh', 'scripts/run_target_environment_acceptance.sh'):
        script = repo_root / script_name
        assert script.exists()
        assert not script.is_symlink()
        result = subprocess.run(['bash', str(script), '--help'], cwd=str(repo_root), text=True, capture_output=True)
        assert result.returncode == 0
        assert 'Usage:' in result.stdout


def test_single_root_release_contains_no_compatibility_shell() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    assert not repo_root.is_symlink()
    for required in ('scripts', 'robot_frontend', 'esp32s3_code', 'stm32_code', 'start_frontend.sh', 'start_ros2_backend.sh', 'start_web_bridge.sh', 'scripts/run_release_verification.sh', 'scripts/run_target_environment_acceptance.sh'):
        target = repo_root / required
        assert target.exists()
        assert not target.is_symlink()
    assert not (repo_root / 'ubuntu_side').exists()
    assert not (repo_root / 'ubuntu_side_upper_computer').exists()


def test_entrypoint_shell_scripts_keep_bash_shebang_in_source_tree() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    for script_name in ('start_frontend.sh', 'start_ros2_backend.sh', 'start_web_bridge.sh', 'scripts/run_release_verification.sh', 'scripts/run_target_environment_acceptance.sh'):
        content = (repo_root / script_name).read_text(encoding='utf-8')
        assert content.startswith('#!/usr/bin/env bash'), script_name
