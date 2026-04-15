from __future__ import annotations

import os
import subprocess
from pathlib import Path


SCRIPT = r'''
set -euo pipefail
source "$REPO_ROOT/scripts/start_surface_common.sh"
export INSPECTION_ROBOT_RUNTIME_DIR="$RUNTIME_ROOT"
export ROBOT_EFFECTIVE_PROFILE="mock"
export ROBOT_EFFECTIVE_CONFIG_ROOT="$CONFIG_ROOT"
export ROBOT_EFFECTIVE_OPERATOR_SESSION_BOOTSTRAP_MODE="local_auto"
ensure_internal_command_runtime
printf '%s\n' "$ROBOT_INTERNAL_COMMAND_RUNTIME_DIR|$ROBOT_INTERNAL_COMMAND_AUTH_TOKEN|$ROBOT_OPERATOR_TOKEN"
'''


def test_runtime_bootstrap_reuses_scope_tokens(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    runtime_root = tmp_path / 'runtime'
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    env = os.environ.copy()
    env['REPO_ROOT'] = str(repo_root)
    env['RUNTIME_ROOT'] = str(runtime_root)
    env['CONFIG_ROOT'] = str(config_root)

    first = subprocess.run(['bash', '-lc', SCRIPT], env=env, check=True, text=True, capture_output=True)
    second = subprocess.run(['bash', '-lc', SCRIPT], env=env, check=True, text=True, capture_output=True)

    first_dir, first_internal, first_operator = first.stdout.strip().split('|')
    second_dir, second_internal, second_operator = second.stdout.strip().split('|')
    assert first_dir == second_dir
    assert first_internal == second_internal
    assert first_operator == second_operator
    assert (Path(first_dir) / 'internal_command_auth.token').is_file()
    assert (Path(first_dir) / 'operator_session.token').is_file()
