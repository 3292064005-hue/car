from __future__ import annotations

"""Repo-audited standard read-only observability bridge runtime.

This runtime provides a localhost-only websocket endpoint that proxies the
repository's observer surface into a deterministic topic-style protocol without
forwarding any client-originated writes. The runtime accepts only read-only
client operations such as subscribe/unsubscribe/list_topics/ping and never
forwards arbitrary publish/service/action messages into ROS.
"""

import argparse
import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import websockets

if __package__ in {None, ''}:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from robot_web_bridge.standard_observability_contract import READONLY_TOPICS

PROTOCOL = 'inspection_robot.readonly_bridge.v1'
DEFAULT_UPSTREAM_URL = 'ws://127.0.0.1:9001/ws'

_TOPIC_BRIDGE_SUMMARY = '/robot/bridge/summary'
_TOPIC_DECISION_SUMMARY = '/robot/decision/summary'
_TOPIC_CONTROL_SUMMARY = '/robot/control/summary'
_TOPIC_NAV_STATUS = '/robot/navigation/status'
_TOPIC_RUNTIME_SUPERVISION = '/robot/runtime/supervision'


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _coerce_jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return str(value)


def _normalize_topics(items: Iterable[Any] | None) -> tuple[str, ...]:
    topics: list[str] = []
    for item in items or ():
        normalized = str(item or '').strip()
        if not normalized:
            continue
        if not normalized.startswith('/'):
            normalized = '/' + normalized.lstrip('/')
        topics.append(normalized)
    return tuple(dict.fromkeys(topics))


@dataclass(slots=True)
class _ClientSession:
    websocket: Any
    subscriptions: set[str]
    connected_at: str = field(default_factory=_now_iso)


class ReadonlyObservabilityBridgeRuntime:
    """Local websocket runtime that republishes observer-surface telemetry.

    Client protocol:
    - bridge_info: server hello and contract snapshot
    - publish: read-only topic publication
    - topics: enumerate available topics
    - subscribed/unsubscribed: subscription change acknowledgement
    - pong: keepalive response
    - error: validation / policy error

    Allowed client ops:
    - ping
    - list_topics
    - subscribe
    - unsubscribe
    """

    def __init__(self, *, host: str, port: int, ws_path: str, upstream_url: str, readonly_topics: Iterable[Any]) -> None:
        self.host = str(host)
        self.port = int(port)
        self.ws_path = str(ws_path)
        self.upstream_url = str(upstream_url or DEFAULT_UPSTREAM_URL)
        self.allowed_topics = _normalize_topics(readonly_topics) or READONLY_TOPICS
        self.clients: dict[Any, _ClientSession] = {}
        self.topic_cache: dict[str, dict[str, Any]] = {}
        self.state: dict[str, Any] = {
            'connection': {},
            'motion': {},
            'power': {},
            'task': {},
            'fault': {},
            'reports': {},
            'transport': {},
            'staleFlags': {},
        }
        self._stop = asyncio.Event()
        self._upstream_ready = asyncio.Event()

    def _bridge_info_message(self) -> dict[str, Any]:
        return {
            'op': 'bridge_info',
            'protocol': PROTOCOL,
            'readonly': True,
            'authorityBoundary': '9100_api_facade_only',
            'writeIngressAllowed': False,
            'topics': list(self.allowed_topics),
            'wsPath': self.ws_path,
            'listenHost': self.host,
            'listenPort': self.port,
            'upstreamUrl': self.upstream_url,
            'runtimeState': 'connected' if self._upstream_ready.is_set() else 'connecting',
            'ts': _now_iso(),
        }

    async def serve(self) -> None:
        server = await websockets.serve(self._handle_client, self.host, self.port, ping_interval=20, ping_timeout=20, max_size=2**20)
        upstream_task = asyncio.create_task(self._upstream_loop())
        try:
            await self._stop.wait()
        finally:
            upstream_task.cancel()
            await asyncio.gather(upstream_task, return_exceptions=True)
            server.close()
            await server.wait_closed()
            for websocket in tuple(self.clients):
                await self._disconnect(websocket)

    async def _disconnect(self, websocket: Any) -> None:
        session = self.clients.pop(websocket, None)
        if session is None:
            return
        try:
            await websocket.close()
        except Exception:
            pass

    async def _send_json(self, websocket: Any, payload: dict[str, Any]) -> None:
        await websocket.send(json.dumps(payload, ensure_ascii=False))

    async def _broadcast(self, payload: dict[str, Any], *, topic: str | None = None) -> None:
        stale: list[Any] = []
        serialized = json.dumps(payload, ensure_ascii=False)
        for websocket, session in tuple(self.clients.items()):
            if topic is not None and topic not in session.subscriptions:
                continue
            try:
                await websocket.send(serialized)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            await self._disconnect(websocket)

    async def _send_cached_topics(self, session: _ClientSession, *, topics: Iterable[str] | None = None) -> None:
        selected = set(_normalize_topics(topics)) if topics is not None else set(session.subscriptions)
        for topic in self.allowed_topics:
            if topic not in selected:
                continue
            cached = self.topic_cache.get(topic)
            if cached is not None:
                await self._send_json(session.websocket, cached)

    async def _handle_client(self, websocket: Any, *args: Any) -> None:
        path = ''
        request = getattr(websocket, 'request', None)
        if getattr(request, 'path', None):
            path = str(request.path)
        elif args:
            path = str(args[0])
        path = path or getattr(websocket, 'path', '') or self.ws_path
        if str(path).split('?', 1)[0] != self.ws_path:
            await websocket.close(code=1008, reason=f'unsupported path: {path}')
            return
        session = _ClientSession(websocket=websocket, subscriptions=set(self.allowed_topics))
        self.clients[websocket] = session
        await self._send_json(websocket, self._bridge_info_message())
        await self._send_cached_topics(session)
        try:
            async for raw in websocket:
                await self._handle_client_message(session, raw)
        finally:
            await self._disconnect(websocket)

    async def _handle_client_message(self, session: _ClientSession, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except Exception:
            await self._send_json(session.websocket, {'op': 'error', 'code': 'READONLY_BRIDGE_INVALID_JSON', 'message': 'message must be valid JSON object', 'ts': _now_iso()})
            return
        if not isinstance(payload, dict):
            await self._send_json(session.websocket, {'op': 'error', 'code': 'READONLY_BRIDGE_INVALID_MESSAGE', 'message': 'message root must be an object', 'ts': _now_iso()})
            return
        op = str(payload.get('op', '') or '').strip()
        if op == 'ping':
            await self._send_json(session.websocket, {'op': 'pong', 'ts': _now_iso()})
            return
        if op == 'list_topics':
            await self._send_json(session.websocket, {'op': 'topics', 'topics': list(self.allowed_topics), 'ts': _now_iso()})
            return
        if op in {'subscribe', 'unsubscribe'}:
            requested = set(_normalize_topics(payload.get('topics', ())))
            rejected = sorted(topic for topic in requested if topic not in self.allowed_topics)
            accepted = sorted(topic for topic in requested if topic in self.allowed_topics)
            if op == 'subscribe':
                session.subscriptions.update(accepted)
                await self._send_json(session.websocket, {'op': 'subscribed', 'topics': accepted, 'rejectedTopics': rejected, 'ts': _now_iso()})
                await self._send_cached_topics(session, topics=accepted)
            else:
                for topic in accepted:
                    session.subscriptions.discard(topic)
                await self._send_json(session.websocket, {'op': 'unsubscribed', 'topics': accepted, 'rejectedTopics': rejected, 'ts': _now_iso()})
            return
        await self._send_json(session.websocket, {
            'op': 'error',
            'code': 'READONLY_BRIDGE_UNSUPPORTED_OP',
            'message': f'unsupported op: {op or "<empty>"}; bridge is read-only and only supports ping/list_topics/subscribe/unsubscribe',
            'ts': _now_iso(),
        })

    async def _upstream_loop(self) -> None:
        while not self._stop.is_set():
            try:
                async with websockets.connect(self.upstream_url, ping_interval=20, ping_timeout=20, max_size=2**20) as upstream:
                    self._upstream_ready.set()
                    await self._broadcast(self._bridge_info_message())
                    async for raw in upstream:
                        updates = self._updates_from_upstream(raw)
                        for topic, source_type, msg in updates:
                            publication = {
                                'op': 'publish',
                                'topic': topic,
                                'msg': _coerce_jsonable(msg),
                                'sourceType': source_type,
                                'readonly': True,
                                'ts': _now_iso(),
                            }
                            self.topic_cache[topic] = publication
                            await self._broadcast(publication, topic=topic)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._upstream_ready.clear()
                await self._broadcast(self._bridge_info_message())
                await asyncio.sleep(1.0)

    def _updates_from_upstream(self, raw: str) -> list[tuple[str, str, dict[str, Any]]]:
        try:
            envelope = json.loads(raw)
        except Exception:
            return []
        if not isinstance(envelope, dict):
            return []
        event_type = str(envelope.get('type', '') or '')
        payload = envelope.get('payload', {}) if isinstance(envelope.get('payload', {}), dict) else {}
        if event_type == 'snapshot':
            self._ingest_snapshot(payload)
            return self._derive_all_topics(source_type='snapshot')
        self._ingest_event(event_type, payload)
        return self._derive_topics_for_event(event_type)

    def _ingest_snapshot(self, payload: dict[str, Any]) -> None:
        self.state['connection'] = dict(payload.get('connection', {})) if isinstance(payload.get('connection', {}), dict) else {}
        self.state['motion'] = dict(payload.get('motion', {})) if isinstance(payload.get('motion', {}), dict) else {}
        self.state['power'] = dict(payload.get('power', {})) if isinstance(payload.get('power', {}), dict) else {}
        self.state['task'] = dict(payload.get('task', {})) if isinstance(payload.get('task', {}), dict) else {}
        self.state['fault'] = dict(payload.get('fault', {})) if isinstance(payload.get('fault', {}), dict) else {}
        self.state['reports'] = dict(payload.get('reports', {})) if isinstance(payload.get('reports', {}), dict) else {}
        self.state['transport'] = dict(payload.get('transport', {})) if isinstance(payload.get('transport', {}), dict) else {}
        self.state['staleFlags'] = dict(payload.get('staleFlags', {})) if isinstance(payload.get('staleFlags', {}), dict) else {}

    def _ingest_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == 'heartbeat':
            self.state['connection'].update(dict(payload))
        elif event_type in {'mode_state', 'chassis_state'}:
            self.state['motion'].update(dict(payload))
        elif event_type == 'power_state':
            self.state['power'].update(dict(payload))
        elif event_type == 'task_event':
            self.state['task'].update(dict(payload))
        elif event_type == 'fault_event':
            self.state['fault'].update(dict(payload))
        elif event_type == 'system_log':
            return

    def _derive_topics_for_event(self, event_type: str) -> list[tuple[str, str, dict[str, Any]]]:
        mapping = {
            'heartbeat': (_TOPIC_BRIDGE_SUMMARY, _TOPIC_RUNTIME_SUPERVISION),
            'mode_state': (_TOPIC_DECISION_SUMMARY, _TOPIC_CONTROL_SUMMARY),
            'chassis_state': (_TOPIC_CONTROL_SUMMARY,),
            'power_state': (_TOPIC_CONTROL_SUMMARY, _TOPIC_RUNTIME_SUPERVISION),
            'task_event': (_TOPIC_DECISION_SUMMARY, _TOPIC_NAV_STATUS),
            'fault_event': (_TOPIC_DECISION_SUMMARY, _TOPIC_RUNTIME_SUPERVISION),
        }
        topics = mapping.get(event_type, ())
        return [item for topic in topics for item in self._derive_topic(topic, source_type=event_type)]

    def _derive_all_topics(self, *, source_type: str) -> list[tuple[str, str, dict[str, Any]]]:
        updates: list[tuple[str, str, dict[str, Any]]] = []
        for topic in self.allowed_topics:
            updates.extend(self._derive_topic(topic, source_type=source_type))
        return updates

    def _derive_topic(self, topic: str, *, source_type: str) -> list[tuple[str, str, dict[str, Any]]]:
        if topic not in self.allowed_topics:
            return []
        payload: dict[str, Any] | None = None
        reports = self.state.get('reports', {}) if isinstance(self.state.get('reports', {}), dict) else {}
        if topic == _TOPIC_BRIDGE_SUMMARY:
            connection = self.state.get('connection', {}) if isinstance(self.state.get('connection', {}), dict) else {}
            payload = {
                'bridgeConnected': bool(connection.get('bridgeConnected', False)),
                'transportLabel': connection.get('transportLabel'),
                'reconnecting': bool(connection.get('reconnecting', False)),
                'latencyMs': connection.get('latencyMs'),
                'heartbeatAgeMs': connection.get('heartbeatAgeMs'),
                'reconnectAttempts': connection.get('reconnectAttempts'),
                'gatewayReady': bool(connection.get('gatewayReady', False)),
                'operatorSurfaceReady': bool(connection.get('operatorSurfaceReady', False)),
                'lastHeartbeatAt': connection.get('lastHeartbeatAt'),
            }
        elif topic == _TOPIC_DECISION_SUMMARY:
            task = self.state.get('task', {}) if isinstance(self.state.get('task', {}), dict) else {}
            motion = self.state.get('motion', {}) if isinstance(self.state.get('motion', {}), dict) else {}
            fault = self.state.get('fault', {}) if isinstance(self.state.get('fault', {}), dict) else {}
            payload = {
                'mode': motion.get('mode'),
                'patrolStatus': task.get('patrolStatus'),
                'currentWaypoint': task.get('currentWaypoint'),
                'actionName': task.get('actionName'),
                'actionPhase': task.get('actionPhase'),
                'commandId': task.get('commandId'),
                'commandType': task.get('commandType'),
                'safeStopActive': bool(fault.get('safeStopActive', False)),
                'estopActive': bool(fault.get('estopActive', False)),
                'faultLevel': fault.get('level'),
                'faultMessage': fault.get('message'),
                'lastUpdateAt': motion.get('lastUpdateAt') or task.get('lastTaskEvent') or fault.get('lastUpdateAt'),
            }
        elif topic == _TOPIC_CONTROL_SUMMARY:
            report = reports.get('controlSummary', {}) if isinstance(reports.get('controlSummary', {}), dict) else {}
            if report:
                payload = dict(report)
            else:
                motion = self.state.get('motion', {}) if isinstance(self.state.get('motion', {}), dict) else {}
                power = self.state.get('power', {}) if isinstance(self.state.get('power', {}), dict) else {}
                payload = {
                    'source': motion.get('commandSource', motion.get('mode', 'unknown')),
                    'linearVelocity': motion.get('linearVelocity'),
                    'angularVelocity': motion.get('angularVelocity'),
                    'leftWheelSpeed': motion.get('leftWheelSpeed'),
                    'rightWheelSpeed': motion.get('rightWheelSpeed'),
                    'lowPowerWarning': bool(power.get('lowPowerWarning', False)),
                    'lastUpdateAt': motion.get('lastUpdateAt') or power.get('lastUpdateAt'),
                }
        elif topic == _TOPIC_NAV_STATUS:
            report = reports.get('navigationStatus', {}) if isinstance(reports.get('navigationStatus', {}), dict) else {}
            if report:
                payload = dict(report)
            else:
                task = self.state.get('task', {}) if isinstance(self.state.get('task', {}), dict) else {}
                payload = {
                    'state': task.get('patrolStatus', 'idle'),
                    'routeName': task.get('currentWaypoint'),
                    'goalLabel': task.get('currentWaypoint'),
                    'progress': task.get('progress', 0),
                    'actionName': task.get('actionName'),
                    'actionPhase': task.get('actionPhase'),
                }
        elif topic == _TOPIC_RUNTIME_SUPERVISION:
            report = reports.get('runtimeSupervision', {}) if isinstance(reports.get('runtimeSupervision', {}), dict) else {}
            if report:
                payload = dict(report)
            else:
                connection = self.state.get('connection', {}) if isinstance(self.state.get('connection', {}), dict) else {}
                fault = self.state.get('fault', {}) if isinstance(self.state.get('fault', {}), dict) else {}
                state = 'ready' if bool(connection.get('gatewayReady', False)) and not bool(fault.get('estopActive', False)) else 'degraded'
                reasons: list[str] = []
                if not bool(connection.get('bridgeConnected', False)):
                    reasons.append('bridge_disconnected')
                if bool(fault.get('safeStopActive', False)):
                    reasons.append('safe_stop_active')
                if bool(fault.get('estopActive', False)):
                    reasons.append('estop_active')
                payload = {
                    'state': state,
                    'reasons': reasons or ['observer_bridge_runtime'],
                    'startupBarrierReady': bool(connection.get('gatewayReady', False)),
                    'operatorSurfaceReady': bool(connection.get('operatorSurfaceReady', False)),
                }
        if payload is None:
            for entry in reports.values():
                if isinstance(entry, dict) and str(entry.get('topic', '') or '') == topic:
                    payload = dict(entry)
                    break
        if payload is None:
            return []
        return [(topic, source_type, payload)]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the repo-audited standard read-only observability bridge runtime.')
    parser.add_argument('--listen-host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--ws-path', default='/observability')
    parser.add_argument('--upstream-url', default=DEFAULT_UPSTREAM_URL)
    parser.add_argument('--readonly-topic', action='append', dest='readonly_topics', default=[])
    parser.add_argument('--dry-run', action='store_true')
    return parser.parse_args(argv)


def _normalized_path(path: str) -> str:
    value = str(path or '/observability').strip() or '/observability'
    return value if value.startswith('/') else '/' + value.lstrip('/')


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ws_path = _normalized_path(str(args.ws_path))
    topics = _normalize_topics(args.readonly_topics) or READONLY_TOPICS
    if args.dry_run:
        payload = {
            'runtime': 'repo_readonly_websocket',
            'listenHost': str(args.listen_host),
            'port': int(args.port),
            'wsPath': ws_path,
            'upstreamUrl': str(args.upstream_url),
            'readonlyTopics': list(topics),
            'protocol': PROTOCOL,
            'authorityBoundary': '9100_api_facade_only',
            'writeIngressAllowed': False,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    runtime = ReadonlyObservabilityBridgeRuntime(host=str(args.listen_host), port=int(args.port), ws_path=ws_path, upstream_url=str(args.upstream_url), readonly_topics=topics)
    try:
        asyncio.run(runtime.serve())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
