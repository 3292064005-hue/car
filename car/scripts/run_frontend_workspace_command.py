#!/usr/bin/env python3
from __future__ import annotations

"""Run one frontend command inside an isolated temporary workspace copy.

This helper keeps canonical source trees clean during verification by copying the
repository into a temporary directory, installing frontend dependencies there,
and executing the requested command from the copied ``robot_frontend`` root.

Args:
    --skip-npm-ci: Reuse existing dependencies inside the temporary workspace.
    --output-json PATH: Optional path for a small execution report.
    --workspace-prefix TEXT: Prefix used for the temporary directory name.
    --: Command to execute from the copied ``robot_frontend`` directory.

Returns:
    Process exit code from the requested command.

Raises:
    SystemExit: If the command is missing, npm/node are unavailable, or one of
        the isolated workspace commands fails.
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / 'robot_frontend'
IGNORE_PATTERNS = (
    'node_modules',
    'dist',
    '.vite',
    'coverage',
    'build',
    'install',
    'log',
    '__pycache__',
    '.pytest_cache',
    '*.pyc',
    '*.pyo',
)


def _run(cmd: Sequence[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(cmd), cwd=str(cwd), text=True, check=True, env=env)


def _copy_repo_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run a frontend command in an isolated temporary workspace copy.')
    parser.add_argument('--skip-npm-ci', action='store_true', help='Skip npm ci in the isolated frontend workspace.')
    parser.add_argument('--output-json', default='', help='Optional JSON execution report path.')
    parser.add_argument('--workspace-prefix', default='inspection_robot_frontend_workspace_', help='Temporary workspace directory prefix.')
    parser.add_argument('command', nargs=argparse.REMAINDER, help='Command to execute after "--".')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = list(args.command)
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        raise SystemExit('missing command; pass it after "--"')
    node = shutil.which('node')
    npm = shutil.which('npm')
    if not node or not npm:
        raise SystemExit('node/npm not found in PATH')

    with tempfile.TemporaryDirectory(prefix=args.workspace_prefix) as tmp_dir:
        repo_copy = Path(tmp_dir) / ROOT.name
        _copy_repo_tree(ROOT, repo_copy)
        copied_frontend = repo_copy / 'robot_frontend'
        env = os.environ.copy()
        env.setdefault('INSPECTION_FRONTEND_ISOLATED_WORKSPACE', '1')
        if not args.skip_npm_ci:
            _run([npm, 'ci', '--no-audit', '--no-fund'], cwd=copied_frontend, env=env)
        completed = _run(command, cwd=copied_frontend, env=env)
        payload = {
            'repo_root': str(ROOT),
            'frontend_root': str(FRONTEND_ROOT),
            'copied_repo_root': str(repo_copy),
            'copied_frontend_root': str(copied_frontend),
            'command': command,
            'skip_npm_ci': bool(args.skip_npm_ci),
            'returncode': completed.returncode,
        }
        if args.output_json:
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
