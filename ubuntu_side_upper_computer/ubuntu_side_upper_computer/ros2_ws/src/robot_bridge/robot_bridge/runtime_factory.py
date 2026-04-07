from __future__ import annotations

"""Shared bridge runtime construction helpers.

The split transport node is the preferred runtime topology. The legacy monolith
now consumes the same transport-stack construction helpers so both topologies
share one implementation path for transport defaults and runtime assembly.
"""

from dataclasses import dataclass
from typing import Any, Callable

from robot_bridge.components.transport_layer import BridgeTransportLayer
from robot_bridge.health_monitor import LinkHealth
from robot_bridge.heartbeat import HeartbeatTracker
from robot_bridge.outbound_queue import OutboundQueue
from robot_bridge.rate_limiter import SimpleRateLimiter
from robot_bridge.reconnect_manager import ReconnectManager
from robot_bridge.tcp_client import TcpJsonClient


DEFAULT_BRIDGE_RUNTIME_SPLIT = True
LEGACY_MONOLITH_RUNTIME_LABEL = 'legacy_monolith'
SPLIT_RUNTIME_LABEL = 'split_runtime'
DEFAULT_BRIDGE_RUNTIME_MODE = SPLIT_RUNTIME_LABEL
SUPPORTED_BRIDGE_RUNTIME_MODES = (SPLIT_RUNTIME_LABEL, LEGACY_MONOLITH_RUNTIME_LABEL)


@dataclass(frozen=True, slots=True)
class BridgeTransportStack:
    host: str
    port: int
    health: LinkHealth
    speak_rate_limiter: SimpleRateLimiter
    reconnect: ReconnectManager
    heartbeat: HeartbeatTracker
    transport: BridgeTransportLayer




def normalize_bridge_runtime_mode(value: Any, *, allow_legacy: bool = True) -> str:
    """Normalize one bridge-runtime selector.

    Args:
        value: Raw runtime selector or compatibility boolean/string.
        allow_legacy: Whether the legacy runtime may be returned.

    Returns:
        Normalized runtime label.

    Raises:
        ValueError: If the selector is unsupported or the legacy path is disabled.
    """
    if isinstance(value, bool):
        normalized = SPLIT_RUNTIME_LABEL if value else LEGACY_MONOLITH_RUNTIME_LABEL
    else:
        raw = str(value or '').strip().lower()
        if raw in {'', 'auto', 'default', 'split', 'split_runtime', 'true', '1', 'yes', 'on'}:
            normalized = SPLIT_RUNTIME_LABEL
        elif raw in {'legacy', 'legacy_monolith', 'monolith', 'false', '0', 'no', 'off'}:
            normalized = LEGACY_MONOLITH_RUNTIME_LABEL
        else:
            raise ValueError(f'unsupported bridge runtime mode: {value!r}')
    if normalized == LEGACY_MONOLITH_RUNTIME_LABEL and not allow_legacy:
        raise ValueError('legacy monolith runtime is compatibility-only; explicit legacy enablement is required')
    return normalized

def declare_transport_parameters(node: Any) -> None:
    """Declare shared transport-layer ROS parameters on one node.

    Args:
        node: ROS node exposing ``declare_parameter``.

    Returns:
        None.

    Raises:
        None.
    """
    node.declare_parameter('host', '127.0.0.1')
    node.declare_parameter('port', 9000)
    node.declare_parameter('heartbeat_period', 1.0)
    node.declare_parameter('heartbeat_timeout_sec', 2.5)
    node.declare_parameter('reconnect_period', 1.0)
    node.declare_parameter('reconnect_max_period', 8.0)
    node.declare_parameter('reconnect_backoff_multiplier', 1.8)
    node.declare_parameter('speak_min_interval', 0.1)
    node.declare_parameter('outbound_queue_size', 64)
    node.declare_parameter('max_drain_per_cycle', 6)
    node.declare_parameter('disconnect_on_heartbeat_timeout', True)



def build_transport_stack(node: Any, *, next_seq: Callable[[], int], logger: Any) -> BridgeTransportStack:
    """Build the shared TCP transport runtime stack.

    Args:
        node: ROS node providing parameter access.
        next_seq: Sequence callback used by the outbound transport layer.
        logger: Logger instance passed to the transport layer.

    Returns:
        ``BridgeTransportStack`` containing the shared transport components.

    Raises:
        None.
    """
    host = str(node.get_parameter('host').value)
    port = int(node.get_parameter('port').value)
    health = LinkHealth()
    speak_rate_limiter = SimpleRateLimiter(float(node.get_parameter('speak_min_interval').value))
    reconnect = ReconnectManager(
        float(node.get_parameter('reconnect_period').value),
        max_period_sec=float(node.get_parameter('reconnect_max_period').value),
        multiplier=float(node.get_parameter('reconnect_backoff_multiplier').value),
    )
    heartbeat = HeartbeatTracker()
    transport = BridgeTransportLayer(
        client=TcpJsonClient(host, port),
        reconnect=reconnect,
        heartbeat=heartbeat,
        outbound=OutboundQueue(max_size=int(node.get_parameter('outbound_queue_size').value)),
        health=health,
        logger=logger,
        next_seq=next_seq,
        max_drain_provider=lambda: int(node.get_parameter('max_drain_per_cycle').value),
    )
    return BridgeTransportStack(
        host=host,
        port=port,
        health=health,
        speak_rate_limiter=speak_rate_limiter,
        reconnect=reconnect,
        heartbeat=heartbeat,
        transport=transport,
    )



def runtime_policy_snapshot() -> dict[str, object]:
    """Return the supported bridge-runtime policy snapshot."""
    return {
        'default_runtime_split': DEFAULT_BRIDGE_RUNTIME_SPLIT,
        'default_runtime_mode': DEFAULT_BRIDGE_RUNTIME_MODE,
        'supported_runtime_modes': list(SUPPORTED_BRIDGE_RUNTIME_MODES),
        'preferred_runtime': SPLIT_RUNTIME_LABEL,
        'rollback_runtime': LEGACY_MONOLITH_RUNTIME_LABEL,
        'legacy_runtime_status': 'compatibility_only',
        'legacy_runtime_accepts_new_features': False,
        'deprecation_notice': 'legacy monolith runtime remains a rollback path and should not receive new feature work',
    }
