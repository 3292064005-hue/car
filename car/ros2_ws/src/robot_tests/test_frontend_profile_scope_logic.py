from __future__ import annotations

import subprocess
from pathlib import Path


def test_frontend_profile_scope_logic_script_passes() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    subprocess.run(
        [
            'python3',
            str(repo_root / 'scripts' / 'run_frontend_workspace_command.py'),
            '--',
            'npm',
            'run',
            'test:profile-scopes',
        ],
        cwd=str(repo_root),
        check=True,
    )
