from __future__ import annotations

import os
import subprocess
from pathlib import Path



def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding='utf-8')
    path.chmod(0o755)



def _ensure_fake_ros_setup(tmp_path: Path) -> Path:
    ros_setup = tmp_path / 'fake_ros' / 'humble' / 'setup.bash'
    ros_setup.parent.mkdir(parents=True, exist_ok=True)
    ros_setup.write_text('#!/usr/bin/env bash\n', encoding='utf-8')
    ros_setup.chmod(0o755)
    return ros_setup



def test_run_release_verification_frontend_calls_expected_steps(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'run_release_verification.sh'
    log_path = tmp_path / 'calls.log'
    fake_ros_setup = _ensure_fake_ros_setup(tmp_path)
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    _write_executable(
        bin_dir / 'python3',
        f"#!/usr/bin/env bash\necho python3:$* >> '{log_path}'\nexit 0\n",
    )

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"
    env['RELEASE_GATE_ROS_SETUP_BASH'] = str(fake_ros_setup)
    env.pop('PYTHONPATH', None)

    subprocess.run(['bash', str(script), '--with-frontend', '--skip-npm-ci'], cwd=str(repo_root), env=env, check=True)
    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert calls[0] == 'python3:scripts/generate_frontend_contract_artifacts.py'
    assert any(line == 'python3:-m pytest -q ros2_ws/src/robot_tests' for line in calls)
    assert 'python3:scripts/check_embedded_source_sync.py' in calls
    assert any(line.startswith('python3:scripts/run_frontend_workspace_command.py -- bash -lc npm run typecheck && npm run build && python3 ../scripts/check_frontend_bundle_budget.py --dist-root dist') for line in calls)
    assert calls[-1] == 'python3:scripts/render_release_quality_manifest.py --output /tmp/release_quality_manifest.json --history-dir /tmp/release_quality_history --profile-report-path /tmp/profile_minimal.json --evidence-report-path /tmp/evidence_report.json --acceptance-report-path /tmp/acceptance_report.json --common-checks-complete true --frontend-lane true --ros-smoke-lane false --integrated-frontend-smoke-lane false'



def test_run_release_verification_forwards_config_root_to_ros_smoke(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'run_release_verification.sh'
    log_path = tmp_path / 'calls.log'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    config_root = tmp_path / 'custom_config_root'
    config_root.mkdir()
    profile_path = config_root / 'launch_profiles.yaml'
    profile_path.write_text('profiles: {}\n', encoding='utf-8')

    fake_ros_setup = _ensure_fake_ros_setup(tmp_path)

    _write_executable(
        bin_dir / 'python3',
        f'''#!/usr/bin/env bash
if [[ "$1" == "-" ]]; then
  echo "{config_root}"
  exit 0
fi
echo python3:$* >> '{log_path}'
exit 0
''',
    )
    _write_executable(
        bin_dir / 'colcon',
        f'''#!/usr/bin/env bash
echo colcon:$* >> '{log_path}'
mkdir -p '{repo_root / 'ros2_ws' / 'install'}'
: > '{repo_root / 'ros2_ws' / 'install' / 'setup.bash'}'
exit 0
''',
    )
    _write_executable(
        bin_dir / 'ros2',
        f"#!/usr/bin/env bash\necho ros2:$* >> '{log_path}'\nexit 0\n",
    )

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"
    env['RELEASE_GATE_ROS_SETUP_BASH'] = str(fake_ros_setup)
    env.pop('PYTHONPATH', None)

    subprocess.run(
        ['bash', str(script), '--with-ros-smoke', '--config-path', str(profile_path)],
        cwd=str(repo_root),
        env=env,
        check=True,
    )
    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert f'python3:scripts/validate_configs.py --config-path {profile_path}' in calls
    assert any(
        line.startswith('python3:scripts/run_live_ros_launch_smoke.py ')
        and f'--launch-arg config_root:={config_root}' in line
        for line in calls
    )
    assert any(line.startswith('colcon:build --symlink-install') for line in calls)



def test_run_release_verification_forwards_config_root_to_integrated_smoke(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'run_release_verification.sh'
    log_path = tmp_path / 'calls.log'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    config_root = tmp_path / 'integrated_config_root'
    config_root.mkdir()

    fake_ros_setup = _ensure_fake_ros_setup(tmp_path)
    install_setup = repo_root / 'ros2_ws' / 'install' / 'setup.bash'
    install_setup.parent.mkdir(parents=True, exist_ok=True)
    install_setup.write_text('#!/usr/bin/env bash\n', encoding='utf-8')

    _write_executable(
        bin_dir / 'python3',
        f'''#!/usr/bin/env bash
if [[ "$1" == "-" ]]; then
  echo "{config_root}"
  exit 0
fi
echo python3:$* >> '{log_path}'
exit 0
''',
    )
    _write_executable(
        bin_dir / 'colcon',
        f"#!/usr/bin/env bash\necho colcon:$* >> '{log_path}'\nexit 0\n",
    )
    _write_executable(
        bin_dir / 'ros2',
        f"#!/usr/bin/env bash\necho ros2:$* >> '{log_path}'\nexit 0\n",
    )

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"
    env['RELEASE_GATE_ROS_SETUP_BASH'] = str(fake_ros_setup)
    env.pop('PYTHONPATH', None)

    subprocess.run(
        ['bash', str(script), '--with-integrated-frontend-smoke', '--skip-npm-ci', '--config-path', str(config_root)],
        cwd=str(repo_root),
        env=env,
        check=True,
    )
    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert any(line.startswith('python3:scripts/run_frontend_workspace_command.py -- bash -lc npm run typecheck && npm run build && python3 ../scripts/check_frontend_bundle_budget.py --dist-root dist') for line in calls)
    assert 'python3:scripts/run_frontend_workspace_command.py -- npm exec playwright install --with-deps chromium' in calls
    assert any(
        line.startswith('python3:scripts/run_integrated_frontend_bridge_smoke.py ')
        and f'--launch-arg config_root:={config_root}' in line
        for line in calls
    )
    assert calls[-1] == 'python3:scripts/render_release_quality_manifest.py --output /tmp/release_quality_manifest.json --history-dir /tmp/release_quality_history --profile-report-path /tmp/profile_minimal.json --evidence-report-path /tmp/evidence_report.json --acceptance-report-path /tmp/acceptance_report.json --common-checks-complete true --frontend-lane true --ros-smoke-lane true --integrated-frontend-smoke-lane true'
