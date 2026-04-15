from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT = r'''
set -euo pipefail
source "$REPO_ROOT/scripts/start_surface_common.sh"
export ROBOT_EFFECTIVE_PROFILE="mock"
export ROBOT_EFFECTIVE_CONFIG_ROOT="$CONFIG_ROOT"
export ROBOT_EFFECTIVE_OPERATOR_SESSION_BOOTSTRAP_MODE="external"
export VITE_ROBOT_SESSION_ROLE="operator"
export VITE_ROBOT_SESSION_TOKEN="SHOULD_NOT_LEAK"
export VITE_ROBOT_SESSION_ID="frontend-session"
bootstrap_surface_runtime frontend "$OUTPUT_PATH"
printf '%s|%s|%s\n' "${VITE_ROBOT_SESSION_ROLE:-}" "${VITE_ROBOT_SESSION_TOKEN:-}" "${VITE_ROBOT_SESSION_ID:-}"
'''


def test_resolver_external_mode_does_not_consume_runtime_operator_token(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
    output = tmp_path / 'resolved.json'
    env = os.environ.copy()
    env['ROBOT_OPERATOR_SESSION_BOOTSTRAP_MODE'] = 'external'
    env['ROBOT_OPERATOR_TOKEN'] = 'SECRET123'
    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'frontend', '--output', str(output)],
        cwd=str(repo_root),
        env=env,
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['runtimeSurface']['operatorSessionBootstrapMode'] == 'external'
    assert payload['frontendEnv']['VITE_ROBOT_SESSION_ROLE'] == ''
    assert payload['frontendEnv']['VITE_ROBOT_SESSION_TOKEN'] == ''
    assert payload['frontendEnv']['VITE_ROBOT_SESSION_ID'] == ''


def test_bootstrap_external_mode_clears_inherited_frontend_session_env(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    output_path = tmp_path / 'surface.env'
    output_path.write_text('', encoding='utf-8')
    env = os.environ.copy()
    env['REPO_ROOT'] = str(repo_root)
    env['CONFIG_ROOT'] = str(tmp_path / 'cfg')
    env['OUTPUT_PATH'] = str(output_path)
    Path(env['CONFIG_ROOT']).mkdir()

    result = subprocess.run(['bash', '-lc', SCRIPT], env=env, check=True, text=True, capture_output=True)
    role, token, session_id = result.stdout.strip().split('|')
    assert role == ''
    assert token == ''
    assert session_id == ''
    content = output_path.read_text(encoding='utf-8')
    assert "export VITE_ROBOT_SESSION_TOKEN=''" in content or 'export VITE_ROBOT_SESSION_TOKEN=""' in content or 'export VITE_ROBOT_SESSION_TOKEN=' in content
