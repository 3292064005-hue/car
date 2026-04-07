from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

try:  # pragma: no cover - depends on full rclpy runtime
    from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
except Exception:  # pragma: no cover - lightweight test stubs may omit callback groups
    MutuallyExclusiveCallbackGroup = None
    ReentrantCallbackGroup = None


@dataclass(frozen=True)
class CallbackGroups:
    """Standard callback-group partition for robot runtime nodes.

    Attributes:
        control: Serialises state-changing command handlers and action callbacks.
        telemetry: Receives high-frequency sensor/state subscriptions.
        io: Handles network/file/bridge I/O callbacks that may block briefly.
        background: Runs summaries, periodic heartbeats and low-priority timers.
    """

    control: Any | None
    telemetry: Any | None
    io: Any | None
    background: Any | None


def build_callback_groups() -> CallbackGroups:
    """Create the standard callback groups when supported by the runtime.

    Returns:
        CallbackGroups with instantiated ROS callback groups, or ``None`` entries when
        callback-group support is unavailable in the current test/runtime environment.

    Raises:
        None.
    """

    def _new(factory: type[Any] | None) -> Any | None:
        if factory is None:
            return None
        return factory()

    return CallbackGroups(
        control=_new(MutuallyExclusiveCallbackGroup),
        telemetry=_new(ReentrantCallbackGroup),
        io=_new(ReentrantCallbackGroup),
        background=_new(MutuallyExclusiveCallbackGroup),
    )


def call_with_callback_group(factory: Callable[..., Any], *args: Any, callback_group: Any | None = None, **kwargs: Any) -> Any:
    """Invoke an rclpy factory while degrading safely in test environments.

    Args:
        factory: Bound ``create_*`` method or other callable.
        *args: Positional arguments forwarded to ``factory``.
        callback_group: Callback group to pass when the runtime supports it.
        **kwargs: Keyword arguments forwarded to ``factory``.

    Returns:
        Result of ``factory``.

    Raises:
        Any exception raised by ``factory`` except a callback-group signature mismatch,
        in which case the call is retried without the ``callback_group`` keyword.
    """
    if callback_group is None:
        return factory(*args, **kwargs)
    try:
        return factory(*args, callback_group=callback_group, **kwargs)
    except TypeError:
        return factory(*args, **kwargs)
