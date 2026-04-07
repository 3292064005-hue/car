from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding='utf-8')
    path.chmod(0o755)


def _fake_python(log_path: Path, report_dir: Path) -> str:
    artifact = report_dir / 'resolved_config_backend.sh'
    return f'''#!/usr/bin/env bash
if [[ "$1" == *"resolve_runtime_surface_config.py" || "$1" == "{Path('scripts/resolve_runtime_surface_config.py')}" ]]; then
  mkdir -p "{report_dir}"
  cat > "{artifact}" <<'EOF'
export ROBOT_EFFECTIVE_CONFIG_ROOT="/tmp/config-root"
export ROBOT_EFFECTIVE_LAUNCH_PROFILES_PATH="/tmp/config-root/launch_profiles.yaml"
export ROBOT_EFFECTIVE_PROFILE="mock"
export ROBOT_EFFECTIVE_SURFACE="backend"
export ROBOT_EFFECTIVE_BRIDGE_HOST="127.0.0.1"
export ROBOT_EFFECTIVE_BRIDGE_PORT="9000"
EOF
  echo python3:$* >> '{log_path}'
  exit 0
fi
echo python3:$* >> '{log_path}'
exit 0
'''


def test_start_backend_runs_preflight_before_build(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'start_ros2_backend.sh'
    ros2_ws = repo_root / 'ros2_ws'
    report_dir = tmp_path / 'reports'
    log_path = tmp_path / 'calls.log'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    install_dir = repo_root / 'ros2_ws' / 'install'
    if install_dir.exists():
        for item in install_dir.rglob('*'):
            if item.is_file():
                item.unlink()
        for item in sorted(install_dir.rglob('*'), reverse=True):
            if item.is_dir():
                item.rmdir()
        install_dir.rmdir()

    _write_executable(bin_dir / 'python3', _fake_python(log_path, report_dir))
    _write_executable(
        bin_dir / 'colcon',
        f"#!/usr/bin/env bash\necho colcon:$* >> '{log_path}'\nmkdir -p '{ros2_ws / 'install'}'\nprintf 'export TEST_SETUP=1\\n' > '{ros2_ws / 'install' / 'setup.bash'}'\nexit 0\n",
    )
    _write_executable(
        bin_dir / 'ros2',
        f"#!/usr/bin/env bash\necho ros2:$* >> '{log_path}'\nexit 0\n",
    )

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"
    env.pop('PYTHONPATH', None)

    subprocess.run([str(script), 'mock', '--preflight-report-dir', str(report_dir)], cwd=str(repo_root), env=env, check=True)

    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert calls[0].startswith('python3:') and 'resolve_runtime_surface_config.py' in calls[0]
    assert calls[1].startswith('python3:-m robot_bringup.preflight')
    assert ' --startup-gate' in calls[1]
    assert calls[2] == 'colcon:build --symlink-install'
    assert calls[3] == 'ros2:launch robot_bringup mock_system.launch.py'


def test_start_backend_skip_preflight_bypasses_gate(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'start_ros2_backend.sh'
    ros2_ws = repo_root / 'ros2_ws'
    report_dir = tmp_path / 'reports'
    log_path = tmp_path / 'calls.log'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    install_dir = repo_root / 'ros2_ws' / 'install'
    if install_dir.exists():
        for item in install_dir.rglob('*'):
            if item.is_file():
                item.unlink()
        for item in sorted(install_dir.rglob('*'), reverse=True):
            if item.is_dir():
                item.rmdir()
        install_dir.rmdir()

    _write_executable(bin_dir / 'python3', _fake_python(log_path, report_dir))
    _write_executable(
        bin_dir / 'colcon',
        f"#!/usr/bin/env bash\necho colcon:$* >> '{log_path}'\nmkdir -p '{ros2_ws / 'install'}'\nprintf 'export TEST_SETUP=1\\n' > '{ros2_ws / 'install' / 'setup.bash'}'\nexit 0\n",
    )
    _write_executable(
        bin_dir / 'ros2',
        f"#!/usr/bin/env bash\necho ros2:$* >> '{log_path}'\nexit 0\n",
    )

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"

    subprocess.run([str(script), 'mock', '--skip-preflight', '--preflight-report-dir', str(report_dir)], cwd=str(repo_root), env=env, check=True)

    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert calls[0].startswith('python3:') and 'resolve_runtime_surface_config.py' in calls[0]
    assert all('-m robot_bringup.preflight' not in line for line in calls)
    assert calls[1:] == ['colcon:build --symlink-install', 'ros2:launch robot_bringup mock_system.launch.py']


def test_start_backend_hardware_does_not_implicitly_build_when_install_missing(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'start_ros2_backend.sh'
    report_dir = tmp_path / 'reports'
    log_path = tmp_path / 'calls.log'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    _write_executable(bin_dir / 'python3', _fake_python(log_path, report_dir))
    _write_executable(
        bin_dir / 'colcon',
        f"#!/usr/bin/env bash\necho colcon:$* >> '{log_path}'\nexit 0\n",
    )
    _write_executable(
        bin_dir / 'ros2',
        f"#!/usr/bin/env bash\necho ros2:$* >> '{log_path}'\nexit 0\n",
    )

    install_dir = repo_root / 'ros2_ws' / 'install'
    if install_dir.exists():
        for item in install_dir.rglob('*'):
            if item.is_file():
                item.unlink()
        for item in sorted(install_dir.rglob('*'), reverse=True):
            if item.is_dir():
                item.rmdir()
        install_dir.rmdir()

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"
    env.pop('PYTHONPATH', None)

    proc = subprocess.run([str(script), 'hardware', '--preflight-report-dir', str(report_dir)], cwd=str(repo_root), env=env, text=True, capture_output=True)

    assert proc.returncode != 0
    assert 'build the workspace first or enable --build-if-needed' in proc.stderr
    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert all(not line.startswith('colcon:') for line in calls)
