#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / 'robot_frontend'


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=True)


def main() -> int:
    node = shutil.which('node')
    npm = shutil.which('npm')
    if not node or not npm:
        raise SystemExit('node/npm not found in PATH')
    if not (FRONTEND_ROOT / 'package-lock.json').exists():
        raise SystemExit('package-lock.json missing; frontend dependency graph is not locked')

    if not (FRONTEND_ROOT / 'node_modules').exists():
        _run([npm, 'ci', '--no-audit', '--no-fund'], cwd=FRONTEND_ROOT)

    test_proc = _run([npm, 'test'], cwd=FRONTEND_ROOT)
    build_proc = _run([npm, 'run', 'build'], cwd=FRONTEND_ROOT)
    dist = FRONTEND_ROOT / 'dist'
    report = {
        'frontend_root': str(FRONTEND_ROOT),
        'package_lock_exists': True,
        'node': node,
        'npm': npm,
        'test_command': 'npm test',
        'build_command': 'npm run build',
        'test_stdout_tail': test_proc.stdout.strip().splitlines()[-5:],
        'build_stdout_tail': build_proc.stdout.strip().splitlines()[-8:],
        'dist_exists': dist.exists(),
        'dist_files': sorted(str(path.relative_to(dist)) for path in dist.rglob('*') if path.is_file())[:20],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
