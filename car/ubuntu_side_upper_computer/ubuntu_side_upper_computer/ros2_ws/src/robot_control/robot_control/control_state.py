from __future__ import annotations

from dataclasses import dataclass, field
from geometry_msgs.msg import Twist
from robot_utils.helpers import monotonic_time


@dataclass
class TimedTwist:
    cmd: Twist = field(default_factory=Twist)
    stamp: float = field(default_factory=monotonic_time)
    valid: bool = False


@dataclass
class ControlSelection:
    source: str = 'idle'
    selected: Twist = field(default_factory=Twist)
    limited: Twist = field(default_factory=Twist)
    ramped: Twist = field(default_factory=Twist)
    final: Twist = field(default_factory=Twist)
    selected_age_sec: float = 0.0
    chassis_age_sec: float = float('inf')
    power_age_sec: float = float('inf')
    safety_latched: bool = False
    safety_reason: str = 'normal'
    power_limited: bool = False
    power_reason: str = 'normal'
