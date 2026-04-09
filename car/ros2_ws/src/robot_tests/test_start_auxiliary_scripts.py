from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding='utf-8')
    path.chmod(0o755)


def _fake_python(log_path: Path, report_dir: Path, *, surface: str, config_root: str = '/tmp/config-root') -> str:
    artifact = report_dir / f'resolved_config_{surface}.sh'
    frontend_exports = """
export VITE_ROBOT_WS_URL=\"ws://127.0.0.1:9001/ws\"
export VITE_ROBOT_MJPEG_URL=\"http://127.0.0.1:8080/stream\"
export VITE_ENABLE_MOCK=\"true\"
export VITE_BRIDGE_LABEL=\"mock-{surface}\"
""".replace('{surface}', surface) if surface == 'frontend' else ''
    return f'''#!/usr/bin/env bash
if [[ "$1" == *"resolve_runtime_surface_config.py" || "$1" == "{Path('scripts/resolve_runtime_surface_config.py')}" ]]; then
  mkdir -p "{report_dir}"
  cat > "{artifact}" <<'EOF'
export ROBOT_EFFECTIVE_CONFIG_ROOT="{config_root}"
export ROBOT_EFFECTIVE_LAUNCH_PROFILES_PATH="{config_root}/launch_profiles.yaml"
export ROBOT_EFFECTIVE_PROFILE="mock"
export ROBOT_EFFECTIVE_SURFACE="{surface}"
export ROBOT_EFFECTIVE_BRIDGE_HOST="127.0.0.1"
export ROBOT_EFFECTIVE_BRIDGE_PORT="9000"
export ROBOT_EFFECTIVE_WS_PUBLIC_HOST="127.0.0.1"
export ROBOT_EFFECTIVE_WS_LISTEN_HOST="0.0.0.0"
export ROBOT_EFFECTIVE_WS_PORT="9001"
export ROBOT_EFFECTIVE_WS_PATH="/ws"
{frontend_exports}
EOF
  echo python3:$* >> '{log_path}'
  exit 0
fi
echo python3:$* >> '{log_path}'
exit 0
'''


def test_start_web_bridge_runs_surface_preflight(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'start_web_bridge.sh'
    ros2_ws = repo_root / 'ros2_ws'
    install_dir = ros2_ws / 'install'
    install_dir.mkdir(exist_ok=True)
    (install_dir / 'setup.bash').write_text('export TEST_SETUP=1\n', encoding='utf-8')
    report_dir = tmp_path / 'reports'
    log_path = tmp_path / 'calls.log'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    _write_executable(bin_dir / 'python3', _fake_python(log_path, report_dir, surface='web_bridge'))
    _write_executable(
        bin_dir / 'ros2',
        f"#!/usr/bin/env bash\necho ros2:$* >> '{log_path}'\nexit 0\n",
    )

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"
    env.pop('PYTHONPATH', None)

    subprocess.run(['bash', str(script), 'mock', '--preflight-report-dir', str(report_dir)], cwd=str(repo_root), env=env, check=True)
    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert 'resolve_runtime_surface_config.py' in calls[0]
    assert '--surface web_bridge' in calls[1]
    assert calls[2].startswith('ros2:run robot_web_bridge web_bridge_node')
    assert '-p listen_host:=0.0.0.0' in calls[2]
    assert '-p listen_port:=9001' in calls[2]
    assert '-p ws_path:=/ws' in calls[2]


def test_start_frontend_generates_contracts_and_runs_surface_preflight(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'start_frontend.sh'
    report_dir = tmp_path / 'reports'
    log_path = tmp_path / 'calls.log'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    _write_executable(bin_dir / 'python3', _fake_python(log_path, report_dir, surface='frontend'))
    _write_executable(
        bin_dir / 'npm',
        f"#!/usr/bin/env bash\necho npm:$* >> '{log_path}'\nexit 0\n",
    )

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"
    env.pop('PYTHONPATH', None)

    subprocess.run(['bash', str(script), 'mock', '--preflight-report-dir', str(report_dir)], cwd=str(repo_root), env=env, check=True)
    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert 'resolve_runtime_surface_config.py' in calls[0]
    assert calls[1].startswith('python3:../scripts/generate_frontend_contract_artifacts.py')
    assert '--surface frontend' in calls[2]
    assert calls[3] == 'npm:run dev'


def test_start_web_bridge_builds_workspace_when_install_missing(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'start_web_bridge.sh'
    report_dir = tmp_path / 'reports'
    log_path = tmp_path / 'calls.log'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    _write_executable(bin_dir / 'python3', _fake_python(log_path, report_dir, surface='web_bridge'))
    _write_executable(
        bin_dir / 'ros2',
        f"#!/usr/bin/env bash\necho ros2:$* >> '{log_path}'\nexit 0\n",
    )
    _write_executable(
        bin_dir / 'colcon',
        f"#!/usr/bin/env bash\necho colcon:$* >> '{log_path}'\nmkdir -p '{repo_root / 'ros2_ws' / 'install'}'\nprintf 'export TEST_SETUP=1\n' > '{repo_root / 'ros2_ws' / 'install' / 'setup.bash'}'\nexit 0\n",
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

    subprocess.run(['bash', str(script), 'mock', '--preflight-report-dir', str(report_dir)], cwd=str(repo_root), env=env, check=True)
    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert 'resolve_runtime_surface_config.py' in calls[0]
    assert '--surface web_bridge' in calls[1]
    assert calls[2].startswith('colcon:build --symlink-install')
    assert calls[3].startswith('ros2:run robot_web_bridge web_bridge_node')
    assert '-p listen_host:=0.0.0.0' in calls[3]


def test_start_frontend_forwards_config_path_to_resolver_and_preflight(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'start_frontend.sh'
    report_dir = tmp_path / 'reports'
    config_root = tmp_path / 'custom-config'
    config_root.mkdir()
    log_path = tmp_path / 'calls.log'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    _write_executable(bin_dir / 'python3', _fake_python(log_path, report_dir, surface='frontend', config_root=str(config_root)))
    _write_executable(
        bin_dir / 'npm',
        f"#!/usr/bin/env bash\necho npm:$* >> '{log_path}'\nexit 0\n",
    )

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"
    env.pop('PYTHONPATH', None)

    subprocess.run(['bash', str(script), 'mock', '--config-path', str(config_root), '--preflight-report-dir', str(report_dir)], cwd=str(repo_root), env=env, check=True)
    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert any('resolve_runtime_surface_config.py' in line and f'--config-path {config_root}' in line for line in calls)
    assert any('-m robot_bringup.preflight' in line and f'--config-path {config_root}' in line for line in calls)
