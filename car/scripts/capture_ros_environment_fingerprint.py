#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> str | None:
    exe = shutil.which(args[0])
    if exe is None:
        return None
    try:
        completed = subprocess.run(args, check=True, capture_output=True, text=True, timeout=15.0)
    except Exception:
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output or None


def main() -> int:
    parser = argparse.ArgumentParser(description='Capture ROS/colcon environment fingerprint for release evidence.')
    parser.add_argument('--workspace-root', default='ros2_ws')
    parser.add_argument('--output', default='/tmp/ros_environment_fingerprint.json')
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root)
    install_setup = workspace_root / 'install' / 'setup.bash'
    payload = {
        'pythonVersion': sys.version.split()[0],
        'rosDistro': os.environ.get('ROS_DISTRO', ''),
        'rosVersion': _run('ros2', '--version'),
        'rosPath': shutil.which('ros2'),
        'colconVersion': _run('colcon', '--version'),
        'colconPath': shutil.which('colcon'),
        'workspaceRoot': str(workspace_root.resolve()),
        'workspaceInstallSetup': str(install_setup.resolve()),
        'workspaceInstallPresent': install_setup.exists(),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
