from __future__ import annotations

from typing import Any, Awaitable, Callable

from robot_web_bridge.ws_transport import WebSocketHub


class WebGateway:
    """Thin component that owns websocket hub lifecycle and sends."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        ws_path: str,
        snapshot_provider: Callable[[], dict[str, Any]],
        command_handler: Callable[[str], Awaitable[None]],
        stats_callback: Callable[[str], None] | Callable[..., None] | None = None,
        telemetry_payload_budget_bytes: int = 64 * 1024,
        control_payload_budget_bytes: int = 128 * 1024,
        snapshot_payload_budget_bytes: int = 256 * 1024,
    ) -> None:
        self._hub = WebSocketHub(
            host=host,
            port=port,
            ws_path=ws_path,
            snapshot_provider=snapshot_provider,
            command_handler=command_handler,
            stats_callback=stats_callback,
            telemetry_payload_budget_bytes=telemetry_payload_budget_bytes,
            control_payload_budget_bytes=control_payload_budget_bytes,
            snapshot_payload_budget_bytes=snapshot_payload_budget_bytes,
        )

    def start(self) -> None:
        """Start the websocket gateway.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        self._hub.start()

    def stop(self) -> None:
        """Stop the websocket gateway.

        Args:
            None.

        Returns:
            None.

        Raises:
            None. Cleanup failures are swallowed because shutdown should remain
            best-effort and must not prevent the owning ROS node from
            completing destruction.
        """
        try:
            self._hub.stop()
        except Exception:
            return

    def schedule_send(self, envelope: dict[str, Any]) -> None:
        """Queue one envelope for websocket broadcast.

        Args:
            envelope: Outbound websocket envelope.

        Returns:
            None.

        Raises:
            None.
        """
        self._hub.schedule_send(envelope)
