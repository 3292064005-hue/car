from __future__ import annotations

"""High-level command-side composition for the web bridge.

The command surface groups ingress validation, bounded admission, lifecycle
tracking, readiness refresh, and runtime-parameter coordination. Keeping these
pieces behind a dedicated facade prevents the transport/runtime projection side
from accumulating command-specific responsibilities.
"""

from dataclasses import dataclass
from typing import Any

from .command_dispatcher import CommandDispatcher
from .command_lifecycle import CommandLifecycleTracker
from .ingress_service import IngressService
from .readiness_cache import ReadinessCache
from .runtime_param_coordinator import RuntimeParamCoordinator

CommandRouter = None


@dataclass(slots=True)
class CommandSurface:
    """Facade exposing command-path collaborators for ``RobotWebBridgeNode``.

    Args:
        node: Bridge node or compatible runtime double.

    Returns:
        None.

    Raises:
        None.
    """

    node: Any
    router: Any
    lifecycle: CommandLifecycleTracker
    runtime_params: RuntimeParamCoordinator
    ingress: IngressService
    readiness: ReadinessCache
    dispatcher: CommandDispatcher

    @classmethod
    def build(cls, *, node: Any) -> 'CommandSurface':
        """Create the fully wired command-side facade.

        Args:
            node: Bridge node or compatible runtime double. The node must expose
                the publishers, service clients, state store, and helper methods
                consumed by the individual command collaborators.

        Returns:
            Fully initialized ``CommandSurface``.

        Raises:
            ValueError: If queue sizing parameters are invalid.
        """
        router_factory = CommandRouter
        if router_factory is None:
            from robot_web_bridge.command_router import CommandRouter as router_factory
        router = router_factory(node, operation_timeout_sec=float(node.get_parameter('command_future_timeout_sec').value))
        lifecycle = CommandLifecycleTracker(store=node.state_store, now_iso=node.now_iso)
        runtime_params = RuntimeParamCoordinator(node=node)
        ingress = IngressService(node=node)
        readiness = ReadinessCache(
            checks={
                '/robot/set_mode': lambda timeout_sec: node.mode_client.wait_for_service(timeout_sec=timeout_sec),
                '/robot/reset_fault': lambda timeout_sec: node.reset_client.wait_for_service(timeout_sec=timeout_sec),
                '/robot/save_snapshot': lambda timeout_sec: node.snapshot_client.wait_for_service(timeout_sec=timeout_sec),
                '/robot/actions/start_patrol': lambda timeout_sec: bool(router.patrol_action_client and router.patrol_action_client.wait_for_server(timeout_sec=timeout_sec)),
                '/robot/actions/track_target': lambda timeout_sec: bool(router.track_action_client and router.track_action_client.wait_for_server(timeout_sec=timeout_sec)),
                '/robot/actions/save_snapshot': lambda timeout_sec: bool(router.snapshot_action_client and router.snapshot_action_client.wait_for_server(timeout_sec=timeout_sec)),
            },
            logger=node.get_logger(),
        )
        dispatcher = CommandDispatcher(
            router_handle=ingress.dispatch_command,
            ack_sender=node.send_ack,
            logger=node.get_logger(),
            max_queue_size=int(node.get_parameter('ingress_queue_max').value),
            reserved_high_priority_slots=int(node.get_parameter('dispatch_reserved_high_priority_slots').value),
            latest_only_types=('teleop_cmd',) if bool(node.get_parameter('teleop_latest_only').value) else (),
            stats_callback=node.on_dispatcher_observation,
            failure_callback=ingress.on_dispatch_failure,
        )
        return cls(node=node, router=router, lifecycle=lifecycle, runtime_params=runtime_params, ingress=ingress, readiness=readiness, dispatcher=dispatcher)
