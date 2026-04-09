from __future__ import annotations

import json
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


def test_run_target_environment_acceptance_fails_when_capture_is_incomplete(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'run_target_environment_acceptance.sh'
    output_path = tmp_path / 'target_environment_acceptance.json'
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    fake_ros_setup = _ensure_fake_ros_setup(tmp_path)

    _write_executable(bin_dir / 'python3', '''#!/usr/bin/env bash
if [[ "$1" == "-c" ]]; then
  exit 0
fi
if [[ "$1" == "scripts/capture_target_environment_acceptance.py" ]]; then
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
  echo '{"schemaVersion": 2, "artifactType": "target_environment_acceptance", "status": "ready_host_harness_only"}' > "$OUTPUT"
  exit 0
fi
exit 0
''')
    _write_executable(bin_dir / 'npm', '#!/usr/bin/env bash\nexit 0\n')
    _write_executable(bin_dir / 'ros2', '#!/usr/bin/env bash\nexit 0\n')
    _write_executable(bin_dir / 'colcon', f'''#!/usr/bin/env bash
mkdir -p '{repo_root / 'ros2_ws' / 'install'}'
: > '{repo_root / 'ros2_ws' / 'install' / 'setup.bash'}'
exit 0
''')

    env = os.environ.copy()
    env['PATH'] = f"{bin_dir}:{env['PATH']}"
    env['RELEASE_GATE_ROS_SETUP_BASH'] = str(fake_ros_setup)
    env.pop('PYTHONPATH', None)

    completed = subprocess.run(['bash', str(script), '--skip-npm-ci', '--output', str(output_path)], cwd=str(repo_root), env=env)
    assert completed.returncode == 4
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['status'] == 'ready_host_harness_only'
