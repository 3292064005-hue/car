from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_ros2_package_metadata import check_python_package, iter_python_packages


def test_python_packages_metadata_ok() -> None:
    results = [check_python_package(path) for path in iter_python_packages()]
    assert results
    assert all(item.ok for item in results), results
