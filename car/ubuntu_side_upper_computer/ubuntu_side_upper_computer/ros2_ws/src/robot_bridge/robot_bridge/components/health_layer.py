from __future__ import annotations

from typing import Any, Callable

from robot_bridge.health_monitor import LinkHealth
from robot_bridge.heartbeat import HeartbeatTracker
from robot_bridge.reconnect_manager import ReconnectManager
from robot_bridge.components.projection_layer import BridgeProjectionLayer


class BridgeHealthLayer:
    """Build bridge transport/health summary independent of transport and projection code."""

    def __init__(
        self,
        *,
        health: LinkHealth,
        reconnect: ReconnectManager,
        heartbeat: HeartbeatTracker,
        projection: BridgeProjectionLayer,
        current_mode_provider: Callable[[], str],
        heartbeat_timeout_provider: Callable[[], float],
        host: str,
        port: int,
    ) -> None:
        self._health = health
        self._reconnect = reconnect
        self._heartbeat = heartbeat
        self._projection = projection
        self._current_mode_provider = current_mode_provider
        self._heartbeat_timeout_provider = heartbeat_timeout_provider
        self._host = host
        self._port = port

    def transport_snapshot(self) -> dict[str, Any]:
        heartbeat_age = round(self._heartbeat.age(), 3) if self._heartbeat.last_rx else None
        summary = self._health.summary()
        summary.update(self._reconnect.summary())
        stale_link = bool(heartbeat_age is not None and heartbeat_age > float(self._heartbeat_timeout_provider()))
        transport_degraded = bool(
            summary.get('transport_degraded', False)
            or stale_link
            or summary.get('reconnect_state') in {'attempting', 'backoff'}
        )
        state = 'stale' if stale_link and self._health.connected else str(summary.get('state', 'connected' if self._health.connected else 'disconnected'))
        if summary.get('reconnect_state') in {'attempting', 'backoff'} and not self._health.connected:
            state = 'reconnecting'
        summary.update(
            {
                'state': state,
                'last_rtt_ms': round(float(self._heartbeat.last_rtt_ms), 3),
                'heartbeat_age_sec': heartbeat_age,
                'stale_link': stale_link,
                'transport_degraded': transport_degraded,
                'current_mode': self._current_mode_provider(),
                'host': self._host,
                'port': self._port,
                'odom': {
                    'x': round(self._projection.odom_state.x, 4),
                    'y': round(self._projection.odom_state.y, 4),
                    'yaw': round(self._projection.odom_state.yaw, 4),
                },
            }
        )
        if self._projection.last_power is not None:
            summary['battery_voltage'] = round(float(self._projection.last_power.battery_voltage), 3)
            summary['battery_percent'] = round(float(self._projection.last_power.battery_percent), 1)
            summary['low_power_warn'] = bool(getattr(self._projection.last_power, 'low_power_warn', False))
            summary['low_power_stop'] = bool(getattr(self._projection.last_power, 'low_power_stop', False))
        if self._projection.last_status is not None:
            summary['wifi_ok'] = bool(self._projection.last_status.wifi_ok)
            summary['camera_ok'] = bool(self._projection.last_status.camera_ok)
            summary['audio_ok'] = bool(self._projection.last_status.audio_ok)
            summary['uart_ok'] = bool(self._projection.last_status.uart_ok)
        if self._projection.last_chassis is not None:
            summary['control_source'] = self._projection.last_chassis.control_source
            summary['estop'] = bool(self._projection.last_chassis.estop)
            summary['heartbeat_ok'] = bool(self._projection.last_chassis.heartbeat_ok)
        return summary
