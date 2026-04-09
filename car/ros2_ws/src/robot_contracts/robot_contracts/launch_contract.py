from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BridgeEndpoint:
    host: str
    port: int
    mjpeg_url: str | None

    @property
    def stream_url(self) -> str | None:
        return self.mjpeg_url


@dataclass(frozen=True, slots=True)
class LaunchRuntime:
    mock_enabled: bool
    bridge: BridgeEndpoint
    web_bridge_enabled: bool = True


MOCK_BRIDGE = BridgeEndpoint(host='127.0.0.1', port=9000, mjpeg_url='http://127.0.0.1:8080/stream')
HARDWARE_BRIDGE = BridgeEndpoint(host='192.168.4.1', port=9000, mjpeg_url='http://192.168.4.1:81/stream')


def normalize_stream_url(*, mjpeg_url: str | None = None, stream_url: str | None = None, default: str | None) -> str | None:
    candidate = str(stream_url or '').strip()
    if candidate:
        return candidate
    candidate = str(mjpeg_url or '').strip()
    if candidate:
        return candidate
    if default is None:
        return None
    candidate = str(default).strip()
    return candidate or None


def resolve_runtime(*, use_mock_robot: bool, bridge_host: str | None = None, bridge_port: int | None = None, mjpeg_url: str | None = None, stream_url: str | None = None, web_bridge_enabled: bool = True, allow_default_stream: bool = True) -> LaunchRuntime:
    base = MOCK_BRIDGE if use_mock_robot else HARDWARE_BRIDGE
    port = int(bridge_port if bridge_port is not None else base.port)
    if port <= 0:
        raise ValueError('bridge_port must be > 0')
    explicit_stream = normalize_stream_url(mjpeg_url=mjpeg_url, stream_url=stream_url, default=None)
    default_stream = base.mjpeg_url if allow_default_stream else None
    bridge = BridgeEndpoint(
        host=str(bridge_host or base.host),
        port=port,
        mjpeg_url=explicit_stream if explicit_stream is not None else default_stream,
    )
    return LaunchRuntime(mock_enabled=use_mock_robot, bridge=bridge, web_bridge_enabled=web_bridge_enabled)
