from __future__ import annotations

"""Helpers for runtime evidence artifacts and canonical ROS package discovery.

This module keeps report/render scripts runnable from the canonical source
workspace and centralizes the runtime evidence directory so scripts stop
falling back to repository-local ``tmp/inspection_robot`` samples.
"""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sys
from typing import Any

from workspace_layout import resolve_workspace_layout

LAYOUT = resolve_workspace_layout(Path(__file__))
CANONICAL_ROOT = LAYOUT.ubuntu_root
ROS_SRC = CANONICAL_ROOT / 'ros2_ws' / 'src'
DEFAULT_RUNTIME_ARTIFACT_DIR = Path(os.environ.get('INSPECTION_ROBOT_RUNTIME_DIR', '/tmp/inspection_robot'))


def extend_ros_import_path() -> None:
    """Add canonical ROS package directories to ``sys.path`` exactly once.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.

    Boundary behavior:
        Missing ROS source roots are ignored so helper scripts can still render
        user-facing diagnostics from partial delivery snapshots.
    """
    if not ROS_SRC.exists():
        return
    for pkg in ROS_SRC.iterdir():
        if pkg.is_dir() and str(pkg) not in sys.path:
            sys.path.insert(0, str(pkg))



def runtime_artifact_dir(path_value: str | Path | None = None) -> Path:
    """Resolve the runtime evidence directory.

    Args:
        path_value: Optional explicit directory override.

    Returns:
        Resolved runtime artifact directory path.

    Raises:
        None.
    """
    if path_value is None or str(path_value).strip() == '':
        return DEFAULT_RUNTIME_ARTIFACT_DIR
    return Path(path_value)



def runtime_metrics_path(path_value: str | Path | None = None) -> Path:
    return runtime_artifact_dir(path_value) / 'metrics.json'



def runtime_evidence_index_path(path_value: str | Path | None = None) -> Path:
    return runtime_artifact_dir(path_value) / 'evidence_index.json'



def runtime_events_path(path_value: str | Path | None = None) -> Path:
    return runtime_artifact_dir(path_value) / 'events.jsonl'



def describe_file(path_value: str | Path) -> dict[str, Any]:
    """Describe one artifact file for provenance/debugging.

    Args:
        path_value: File path to inspect.

    Returns:
        Serializable metadata dictionary.

    Raises:
        None. Non-existent or unreadable files are reported as missing.
    """
    path = Path(path_value)
    payload: dict[str, Any] = {
        'path': str(path),
        'exists': path.exists(),
        'isFile': path.is_file(),
        'sizeBytes': None,
        'modifiedAtUtc': None,
        'sha256': None,
    }
    if not path.exists() or not path.is_file():
        return payload
    stat = path.stat()
    payload['sizeBytes'] = stat.st_size
    payload['modifiedAtUtc'] = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    payload['sha256'] = digest.hexdigest()
    return payload
