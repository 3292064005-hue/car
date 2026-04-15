from __future__ import annotations

import sys
from pathlib import Path


def test_pytest_source_bootstrap_exposes_ros_packages() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    ros_src_root = repo_root / 'ros2_ws' / 'src'
    missing = [str(pkg) for pkg in sorted(ros_src_root.iterdir()) if pkg.is_dir() and str(pkg) not in sys.path]
    assert missing == []
