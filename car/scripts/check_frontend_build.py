#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / 'robot_frontend'


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=True)


def _copy_repo_tree(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(
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
        ),
    )


def main() -> int:
    node = shutil.which('node')
    npm = shutil.which('npm')
    if not node or not npm:
        raise SystemExit('node/npm not found in PATH')
    if not (FRONTEND_ROOT / 'package-lock.json').exists():
        raise SystemExit('package-lock.json missing; frontend dependency graph is not locked')

    with tempfile.TemporaryDirectory(prefix='inspection_robot_frontend_build_') as tmp_dir:
        repo_copy = Path(tmp_dir) / ROOT.name
        _copy_repo_tree(ROOT, repo_copy)
        work_root = repo_copy / 'robot_frontend'
        _run([npm, 'ci', '--no-audit', '--no-fund'], cwd=work_root)
        test_proc = _run([npm, 'test'], cwd=work_root)
        build_proc = _run([npm, 'run', 'build'], cwd=work_root)
        dist = work_root / 'dist'
        report = {
            'frontend_root': str(FRONTEND_ROOT),
            'work_root': str(work_root),
            'package_lock_exists': True,
            'node': node,
            'npm': npm,
            'test_command': 'npm test',
            'build_command': 'npm run build',
            'test_stdout_tail': test_proc.stdout.strip().splitlines()[-5:],
            'build_stdout_tail': build_proc.stdout.strip().splitlines()[-8:],
            'dist_exists': dist.exists(),
            'dist_files': sorted(str(path.relative_to(dist)) for path in dist.rglob('*') if path.is_file())[:20],
            'worktree_mutated': False,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
