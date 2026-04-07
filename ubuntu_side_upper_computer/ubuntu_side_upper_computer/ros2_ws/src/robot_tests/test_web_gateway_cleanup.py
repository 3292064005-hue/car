from __future__ import annotations

from robot_web_bridge.components.web_gateway import WebGateway


class _BoomHub:
    def stop(self) -> None:
        raise RuntimeError('cleanup failed')


def test_web_gateway_stop_swallows_cleanup_error() -> None:
    gateway = WebGateway(
        host='127.0.0.1',
        port=9001,
        ws_path='/ws',
        snapshot_provider=lambda: {},
        command_handler=lambda raw: None,
    )
    gateway._hub = _BoomHub()  # type: ignore[attr-defined]
    gateway.stop()
