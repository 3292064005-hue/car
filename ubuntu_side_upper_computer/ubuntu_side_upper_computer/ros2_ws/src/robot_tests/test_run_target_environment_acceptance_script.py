from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding='utf-8')
    path.chmod(0o755)


def _ensure_fake_ros_setup() -> None:
    ros_setup = Path('/opt/ros/humble/setup.bash')
    ros_setup.parent.mkdir(parents=True, exist_ok=True)
    ros_setup.write_text('#!/usr/bin/env bash\n', encoding='utf-8')


def test_run_target_environment_acceptance_executes_release_verification_and_capture(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'run_target_environment_acceptance.sh'
    log_path = tmp_path / 'calls.log'
    output_path = tmp_path / 'target_environment_acceptance.json'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    _ensure_fake_ros_setup()

    _write_executable(
        bin_dir / 'python3',
        f'''#!/usr/bin/env bash
if [[ "$1" == "-c" ]]; then
  echo python3:$* >> '{log_path}'
  exit 0
fi
if [[ "$1" == "scripts/capture_target_environment_acceptance.py" ]]; then
  echo python3:$* >> '{log_path}'
  shift
  OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --output)
        shift
        OUTPUT="$1"
        ;;
    esac
    shift || true
  done
  mkdir -p "$(dirname "$OUTPUT")"
  echo '{{"status": "ready"}}' > "$OUTPUT"
  exit 0
fi
echo python3:$* >> '{log_path}'
exit 0
''',
    )
    _write_executable(
        bin_dir / 'npm',
        f"#!/usr/bin/env bash\necho npm:$* >> '{log_path}'\nexit 0\n",
    )
    _write_executable(
        bin_dir / 'ros2',
        f"#!/usr/bin/env bash\necho ros2:$* >> '{log_path}'\nexit 0\n",
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

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"
    env.pop('PYTHONPATH', None)

    subprocess.run([str(script), '--skip-npm-ci', '--output', str(output_path)], cwd=str(repo_root), env=env, check=True)
    calls = log_path.read_text(encoding='utf-8').splitlines()
    assert any(line.startswith('python3:-c import rclpy') for line in calls)
    assert any(line.startswith('python3:scripts/render_release_quality_manifest.py ') for line in calls)
    assert any(line.startswith('python3:scripts/capture_target_environment_acceptance.py --output ') for line in calls)
    assert output_path.exists()
