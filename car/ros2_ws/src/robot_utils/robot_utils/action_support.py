from __future__ import annotations

from importlib import import_module
from typing import Any


def load_robot_actions() -> dict[str, Any]:
    """Best-effort load of generated ROS action classes.

    Returns:
        Mapping of action class names to generated classes, or an empty mapping when
        action interfaces are not built in the current environment.

    Raises:
        None.
    """
    try:
        module = import_module('robot_msgs.action')
    except Exception:
        return {}
    result: dict[str, Any] = {}
    for name in ('StartPatrol', 'TrackTarget', 'SaveSnapshotTask'):
        value = getattr(module, name, None)
        if value is not None:
            result[name] = value
    return result


def action_support_enabled() -> bool:
    """Return whether generated action classes are available in the current process."""
    actions = load_robot_actions()
    return all(name in actions for name in ('StartPatrol', 'TrackTarget', 'SaveSnapshotTask'))
