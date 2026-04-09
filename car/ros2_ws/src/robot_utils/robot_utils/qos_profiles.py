from __future__ import annotations

from dataclasses import dataclass

try:
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
except Exception:  # pragma: no cover - lightweight test stubs may omit qos module
    class _EnumValue(str):
        pass

    class HistoryPolicy:
        KEEP_LAST = _EnumValue("KEEP_LAST")

    class ReliabilityPolicy:
        RELIABLE = _EnumValue("RELIABLE")
        BEST_EFFORT = _EnumValue("BEST_EFFORT")

    class DurabilityPolicy:
        VOLATILE = _EnumValue("VOLATILE")

    class QoSProfile:
        def __init__(self, *, history, depth, reliability, durability):
            self.history = history
            self.depth = depth
            self.reliability = reliability
            self.durability = durability


@dataclass(frozen=True)
class QosMatrix:
    """Named QoS profiles used across the robot stack.

    The matrix keeps topic semantics explicit instead of relying on ad-hoc queue depths.
    Control and fault paths remain reliable with low history, while perception/telemetry
    paths prefer lower buffering and best-effort delivery where stale samples are worse
    than dropped samples.
    """

    control_cmd: QoSProfile
    mode_state: QoSProfile
    fault_event: QoSProfile
    status_summary: QoSProfile
    telemetry: QoSProfile
    perception: QoSProfile
    event_log: QoSProfile


QOS_MATRIX = QosMatrix(
    control_cmd=QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=5,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    ),
    mode_state=QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    ),
    fault_event=QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    ),
    status_summary=QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    ),
    telemetry=QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=5,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    ),
    perception=QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=5,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
    ),
    event_log=QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=50,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    ),
)


def qos_for(channel: str) -> QoSProfile:
    """Return the named QoS profile for one logical channel.

    Args:
        channel: Matrix channel name.

    Returns:
        QoSProfile instance.

    Raises:
        KeyError: If the channel name is unsupported.
    """
    mapping = {
        'control_cmd': QOS_MATRIX.control_cmd,
        'mode_state': QOS_MATRIX.mode_state,
        'fault_event': QOS_MATRIX.fault_event,
        'status_summary': QOS_MATRIX.status_summary,
        'telemetry': QOS_MATRIX.telemetry,
        'perception': QOS_MATRIX.perception,
        'event_log': QOS_MATRIX.event_log,
    }
    if channel not in mapping:
        raise KeyError(f'unknown qos channel: {channel}')
    return mapping[channel]
