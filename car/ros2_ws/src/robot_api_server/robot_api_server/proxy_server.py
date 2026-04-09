from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Iterable

from aiohttp import ClientSession, WSMsgType, web

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from robot_contracts.bridge_contract import COMMAND_TYPES
from robot_contracts.command_policy import SessionPolicy, resolve_session_policy


@dataclass
class UpstreamMirror:
    """In-memory mirror of upstream bridge state used by the API layer.

    Attributes:
        latest_event: Most recent upstream event payload.
        latest_snapshot: Most recent snapshot-like payload.
        command_log: Recent command submissions observed by the API.
        event_log: Recent upstream events forwarded to API clients.
        connected: Whether the upstream websocket is currently connected.
    """

    latest_event: dict[str, Any] | None = None
    latest_snapshot: dict[str, Any] | None = None
    command_log: Deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=128))
    event_log: Deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=256))
    connected: bool = False
    reconnect_attempts: int = 0
    latest_connection: dict[str, Any] | None = None
    latest_reports: dict[str, Any] | None = None


class RobotApiProxyServer:
    """HTTP and WebSocket API facade in front of ``robot_web_bridge``.

    The server maintains a local state mirror so frontend clients can query health,
    runtime metadata, and the latest snapshot without coupling directly to the ROS
    bridge transport. The local WebSocket endpoint is a policy-enforcing proxy with
    local fan-out and command auditing.
    """

    def __init__(
        self,
        *,
        upstream_url: str,
        listen_host: str,
        listen_port: int,
        ws_path: str = '/ws',
        api_prefix: str = '/api/v1',
        default_role: str = 'observer',
        require_operator_token: bool = True,
        operator_tokens: Iterable[str] = (),
        upstream_session_role: str = 'observer',
        upstream_session_id: str = 'robot-api-server-mirror',
        upstream_session_token: str = '',
        internal_command_socket_path: str = '/tmp/inspection_robot/bridge_internal_command.sock',
        internal_command_auth_token: str = '',
    ) -> None:
        self.upstream_url = upstream_url
        self.listen_host = listen_host
        self.listen_port = int(listen_port)
        self.ws_path = ws_path if ws_path.startswith('/') else '/' + ws_path.lstrip('/')
        self.api_prefix = api_prefix.rstrip('/') or '/api/v1'
        self.default_role = str(default_role or 'observer').strip().lower() or 'observer'
        self.require_operator_token = bool(require_operator_token)
        self.operator_tokens = {str(item).strip() for item in operator_tokens if str(item).strip()}
        self.upstream_session_role = str(upstream_session_role or 'observer').strip() or 'observer'
        self.upstream_session_id = str(upstream_session_id or 'robot-api-server-mirror').strip() or 'robot-api-server-mirror'
        self.upstream_session_token = str(upstream_session_token or '').strip()
        self.internal_command_socket_path = str(internal_command_socket_path or '/tmp/inspection_robot/bridge_internal_command.sock').strip() or '/tmp/inspection_robot/bridge_internal_command.sock'
        self.internal_command_auth_token = str(internal_command_auth_token or '').strip()
        self._internal_command_registered = False
        self._internal_command_lease_epoch: int | None = None
        self.mirror = UpstreamMirror()
        self._client_session: ClientSession | None = None
        self._upstream_ws = None
        self._app = web.Application()
        self._app.add_routes([
            web.get(f'{self.api_prefix}/health', self.handle_health),
            web.get(f'{self.api_prefix}/state', self.handle_state),
            web.get(f'{self.api_prefix}/runtime', self.handle_runtime),
            web.get(f'{self.api_prefix}/logs', self.handle_logs),
            web.post(f'{self.api_prefix}/commands', self.handle_command),
            web.get(self.ws_path, self.handle_ws),
        ])
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._local_clients: dict[web.WebSocketResponse, SessionPolicy] = {}
        self._upstream_task: asyncio.Task[None] | None = None
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        """Start the HTTP server and upstream websocket mirror.

        Returns:
            None.

        Raises:
            RuntimeError: If the server is started more than once.
        """
        if self._runner is not None:
            raise RuntimeError('server already started')
        self._client_session = ClientSession()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.listen_host, self.listen_port)
        await self._site.start()
        if self.internal_command_socket_path and self.internal_command_auth_token:
            await self._register_internal_command_client()
        self._upstream_task = asyncio.create_task(self._mirror_upstream())

    async def stop(self) -> None:
        """Stop the API server and close upstream/local websocket sessions.

        Returns:
            None.

        Raises:
            None. Best-effort cleanup is always attempted.
        """
        self._shutdown.set()
        if self._upstream_task is not None:
            self._upstream_task.cancel()
            with __import__('contextlib').suppress(asyncio.CancelledError):
                await self._upstream_task
        for client in list(self._local_clients):
            await client.close(code=1001, message=b'server shutdown')
        self._local_clients.clear()
        if self._upstream_ws is not None:
            await self._upstream_ws.close()
        if self._client_session is not None:
            await self._client_session.close()
            self._client_session = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    def _resolve_policy(
        self,
        *,
        requested_role: str = '',
        token: str = '',
        session_id: str = '',
        source: str = 'default',
    ) -> SessionPolicy:
        return resolve_session_policy(
            requested_role=requested_role,
            token=token,
            session_id=session_id,
            default_role=self.default_role,
            require_operator_token=self.require_operator_token,
            operator_tokens=tuple(sorted(self.operator_tokens)),
            source=source,
        )

    def _request_policy(self, request: web.Request) -> SessionPolicy:
        headers = request.headers
        query = request.query
        role = str(headers.get('X-Robot-Session-Role', query.get('role', query.get('sessionRole', ''))))
        token = str(headers.get('X-Robot-Session-Token', query.get('token', query.get('sessionToken', ''))))
        session_id = str(headers.get('X-Robot-Session-Id', query.get('sessionId', '')))
        source = 'request' if role or token or session_id else 'default'
        return self._resolve_policy(requested_role=role, token=token, session_id=session_id, source=source)

    def _command_denied_payload(self, payload: dict[str, Any], policy: SessionPolicy) -> dict[str, Any]:
        command_id = str(payload.get('eventId', '') or payload.get('commandId', '') or '')
        command_type = str(payload.get('type', '') or 'unknown')
        return {
            'type': 'command_ack',
            'payload': {
                'commandId': command_id,
                'commandType': command_type,
                'status': 'denied',
                'lifecycleStatus': 'denied',
                'message': 'command rejected by authoritative API session policy',
                'detail': policy.reason,
                'sessionRole': policy.role,
                'sessionId': policy.session_id,
            },
        }

    def _overlay_command_permissions(self, connection: dict[str, Any], policy: SessionPolicy) -> dict[str, Any]:
        payload = dict(connection or {})
        if policy.write_enabled:
            payload.setdefault('sessionRole', policy.role)
            payload.setdefault('sessionRequestedRole', policy.requested_role)
            payload.setdefault('sessionWriteEnabled', True)
            payload.setdefault('sessionAccessReason', policy.reason)
            payload.setdefault('sessionId', policy.session_id)
            payload.setdefault('sessionPolicySource', policy.source)
            return payload
        permissions = dict(payload.get('commandPermissions') or {})
        for command in COMMAND_TYPES:
            permissions[command] = {
                'allowed': False,
                'reason': policy.reason,
            }
        payload.update({
            'allowedTargetModes': [],
            'modeReasons': {},
            'commandPermissions': permissions,
            'sessionRole': policy.role,
            'sessionRequestedRole': policy.requested_role,
            'sessionWriteEnabled': False,
            'sessionAccessReason': policy.reason,
            'sessionId': policy.session_id,
            'sessionPolicySource': policy.source,
        })
        return payload

    def _apply_policy_to_event(self, event: dict[str, Any] | None, policy: SessionPolicy) -> dict[str, Any] | None:
        if not isinstance(event, dict):
            return event
        cloned = dict(event)
        if cloned.get('type') == 'snapshot' and isinstance(cloned.get('payload'), dict):
            payload = dict(cloned['payload'])
            payload['connection'] = self._overlay_command_permissions(dict(payload.get('connection') or {}), policy)
            cloned['payload'] = payload
            return cloned
        if cloned.get('type') in {'heartbeat', 'connection_state'} and isinstance(cloned.get('payload'), dict):
            cloned['payload'] = self._overlay_command_permissions(dict(cloned['payload']), policy)
            return cloned
        return cloned


    def _resolved_upstream_url(self) -> str:
        """Return the upstream websocket URL augmented with the read-only mirror session.

        Returns:
            Upstream URL with mirror role/session query parameters applied.

        Raises:
            None. Invalid base URLs are returned unchanged.
        """
        try:
            parsed = urlsplit(self.upstream_url)
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if self.upstream_session_role:
                query['role'] = self.upstream_session_role
            if self.upstream_session_id:
                query['sessionId'] = self.upstream_session_id
            if self.upstream_session_token:
                query['token'] = self.upstream_session_token
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
        except Exception:
            return self.upstream_url

    async def _register_internal_command_client(self) -> None:
        if not self.internal_command_socket_path or not self.internal_command_auth_token:
            raise RuntimeError('internal command socket authentication is not configured')
        attempts = 0
        last_message = 'internal command registration failed'
        while attempts < 20:
            attempts += 1
            response = await self._dispatch_internal_command({'type': '__register_internal_client__'}, require_registration=False)
            if bool(response.get('ok', False)):
                self._internal_command_registered = True
                self._internal_command_lease_epoch = int(response.get('leaseEpoch', 0) or 0) or None
                return
            last_message = str(response.get('message', last_message) or last_message)
            await asyncio.sleep(0.1)
        raise RuntimeError(last_message)

    async def _dispatch_internal_command(self, payload: dict[str, Any], *, require_registration: bool = True) -> dict[str, Any]:
        if not self.internal_command_socket_path:
            return {'ok': False, 'message': 'internal command socket path is not configured'}
        if not self.internal_command_auth_token:
            return {'ok': False, 'message': 'internal command socket auth token is not configured'}
        if require_registration and not self._internal_command_registered:
            await self._register_internal_command_client()
        reader = writer = None
        try:
            reader, writer = await asyncio.open_unix_connection(self.internal_command_socket_path)
            outbound = dict(payload)
            outbound['__internalCommandAuthToken'] = self.internal_command_auth_token
            if self._internal_command_lease_epoch is not None:
                outbound['__internalCommandLeaseEpoch'] = self._internal_command_lease_epoch
            writer.write((json.dumps(outbound, ensure_ascii=False) + '\n').encode('utf-8'))
            await writer.drain()
            raw = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not raw:
                return {'ok': False, 'message': 'internal command socket closed without a response'}
            response = json.loads(raw.decode('utf-8'))
            if isinstance(response, dict) and str(response.get('message', '') or '') == 'internal command socket lease epoch mismatch':
                self._internal_command_registered = False
                self._internal_command_lease_epoch = None
                if require_registration:
                    await self._register_internal_command_client()
                    return await self._dispatch_internal_command(payload, require_registration=False)
            return response if isinstance(response, dict) else {'ok': False, 'message': 'internal command socket returned non-object response'}
        except FileNotFoundError:
            return {'ok': False, 'message': f'internal command socket unavailable: {self.internal_command_socket_path}'}
        except Exception as exc:
            return {'ok': False, 'message': f'internal command dispatch failed: {exc}'}
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

    async def _broadcast_local(self, payload: dict[str, Any]) -> None:
        closed: list[web.WebSocketResponse] = []
        for client, policy in list(self._local_clients.items()):
            try:
                message = self._apply_policy_to_event(payload, policy)
                await client.send_str(json.dumps(message, ensure_ascii=False))
            except Exception:
                closed.append(client)
        for client in closed:
            self._local_clients.pop(client, None)

    async def _mirror_upstream(self) -> None:
        """Continuously mirror the upstream bridge websocket into local state.

        Returns:
            None.

        Raises:
            None. Disconnects trigger retry with backoff.
        """
        assert self._client_session is not None
        while not self._shutdown.is_set():
            try:
                async with self._client_session.ws_connect(self._resolved_upstream_url(), heartbeat=15.0) as upstream:
                    self._upstream_ws = upstream
                    self.mirror.connected = True
                    self.mirror.reconnect_attempts = 0
                    async for message in upstream:
                        if message.type != WSMsgType.TEXT:
                            continue
                        payload = json.loads(message.data)
                        self.mirror.latest_event = payload
                        if payload.get('type') in {'snapshot', 'connection_state'} or 'payload' in payload:
                            self.mirror.latest_snapshot = payload
                        connection_payload = self._extract_connection_payload(payload)
                        if connection_payload:
                            self.mirror.latest_connection = connection_payload
                        reports_payload = self._extract_reports_payload(payload)
                        if reports_payload:
                            self.mirror.latest_reports = reports_payload
                        self.mirror.event_log.append(payload)
                        await self._broadcast_local(payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.mirror.connected = False
                self.mirror.reconnect_attempts += 1
                self.mirror.event_log.append({'type': 'api_upstream_error', 'payload': {'message': str(exc)}})
                await asyncio.sleep(min(3.0, 0.4 * max(1, self.mirror.reconnect_attempts)))
            else:
                self.mirror.connected = False
                await asyncio.sleep(0.2)
            finally:
                self._upstream_ws = None

    @staticmethod
    def _extract_connection_payload(event: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(event, dict):
            return {}
        payload = event.get('payload')
        if event.get('type') == 'snapshot' and isinstance(payload, dict):
            return dict(payload.get('connection') or {})
        if event.get('type') in {'heartbeat', 'connection_state'} and isinstance(payload, dict):
            return dict(payload)
        return {}

    @staticmethod
    def _extract_reports_payload(event: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(event, dict):
            return {}
        payload = event.get('payload')
        if event.get('type') == 'snapshot' and isinstance(payload, dict):
            reports = payload.get('reports')
            if isinstance(reports, dict):
                return dict(reports)
        return {}

    def _health_payload(self, policy: SessionPolicy | None = None) -> dict[str, Any]:
        effective_policy = policy or self._resolve_policy()
        connection = self._overlay_command_permissions(dict(self.mirror.latest_connection or {}), effective_policy)
        operator_ready = bool(connection.get('operatorReady'))
        runtime_health_state = str(connection.get('runtimeHealthState') or ('ready' if self.mirror.connected else 'unavailable'))
        runtime_health_reasons = list(connection.get('runtimeHealthReasons') or ([] if self.mirror.connected else ['api_upstream_disconnected']))
        operator_ready_reasons = list(connection.get('operatorReadyReasons') or ([] if operator_ready else ['operator_surface_not_ready']))
        service_ok = bool(self.mirror.connected)
        return {
            'ok': service_ok,
            'ready': bool(service_ok and operator_ready),
            'operatorReady': operator_ready,
            'operatorReadyReasons': operator_ready_reasons,
            'operatorReadyTopic': connection.get('operatorReadyTopic'),
            'upstreamConnected': self.mirror.connected,
            'runtimeHealthState': runtime_health_state,
            'runtimeHealthReasons': runtime_health_reasons,
            'reconnectAttempts': self.mirror.reconnect_attempts,
            'localClientCount': len(self._local_clients),
            'sessionRole': effective_policy.role,
            'sessionRequestedRole': effective_policy.requested_role,
            'sessionWriteEnabled': effective_policy.write_enabled,
            'sessionAccessReason': effective_policy.reason,
            'sessionId': effective_policy.session_id,
            'sessionPolicySource': effective_policy.source,
        }

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response(self._health_payload(self._request_policy(request)))

    async def handle_state(self, request: web.Request) -> web.Response:
        policy = self._request_policy(request)
        return web.json_response({
            'latestEvent': self._apply_policy_to_event(self.mirror.latest_event, policy),
            'latestSnapshot': self._apply_policy_to_event(self.mirror.latest_snapshot, policy),
            'latestConnection': self._overlay_command_permissions(dict(self.mirror.latest_connection or {}), policy),
            'latestReports': self.mirror.latest_reports,
            'upstreamConnected': self.mirror.connected,
        })

    async def handle_runtime(self, request: web.Request) -> web.Response:
        policy = self._request_policy(request)
        return web.json_response({
            'listenHost': self.listen_host,
            'listenPort': self.listen_port,
            'wsPath': self.ws_path,
            'apiPrefix': self.api_prefix,
            'upstreamUrl': self.upstream_url,
            'externalCommandEntry': 'robot_api_server',
            'upstreamBridgeRole': 'robot_web_bridge',
            'operatorSurfaceContract': self._health_payload(policy),
            'accessPolicy': {
                'defaultRole': self.default_role,
                'requireOperatorToken': self.require_operator_token,
                'effectiveRole': policy.role,
                'effectiveWriteEnabled': policy.write_enabled,
                'effectiveReason': policy.reason,
            },
        })

    async def handle_logs(self, request: web.Request) -> web.Response:
        policy = self._request_policy(request)
        return web.json_response({
            'commands': list(self.mirror.command_log),
            'events': list(self.mirror.event_log),
            'session': {
                'role': policy.role,
                'writeEnabled': policy.write_enabled,
                'reason': policy.reason,
                'sessionId': policy.session_id,
            },
        })

    async def handle_command(self, request: web.Request) -> web.Response:
        policy = self._request_policy(request)
        try:
            payload = await request.json()
        except Exception as exc:
            return web.json_response({'ok': False, 'message': f'invalid json payload: {exc}'}, status=400)
        if not isinstance(payload, dict):
            return web.json_response({'ok': False, 'message': 'json payload must be an object'}, status=400)
        command_type = str(payload.get('type', '') or '')
        log_record = {'source': 'http', 'payload': payload, 'sessionRole': policy.role, 'sessionId': policy.session_id}
        self.mirror.command_log.append(log_record)
        if command_type in COMMAND_TYPES and not policy.write_enabled:
            return web.json_response({'ok': False, 'message': policy.reason, 'sessionRole': policy.role, 'sessionId': policy.session_id}, status=403)
        dispatch = await self._dispatch_internal_command(payload)
        if not bool(dispatch.get('ok', False)):
            return web.json_response({'ok': False, 'message': str(dispatch.get('message', 'internal command dispatch failed')), 'sessionRole': policy.role, 'sessionId': policy.session_id}, status=503)
        return web.json_response({'ok': True, 'forwarded': True, 'transport': 'internal_command_socket', 'sessionRole': policy.role, 'sessionId': policy.session_id})

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        policy = self._request_policy(request)
        ws = web.WebSocketResponse(heartbeat=20.0)
        await ws.prepare(request)
        self._local_clients[ws] = policy
        if self.mirror.latest_snapshot is not None:
            latest = self._apply_policy_to_event(self.mirror.latest_snapshot, policy)
            await ws.send_str(json.dumps(latest, ensure_ascii=False))
        try:
            async for message in ws:
                if message.type != WSMsgType.TEXT:
                    continue
                try:
                    payload = json.loads(message.data)
                except Exception as exc:
                    await ws.send_str(json.dumps({'type': 'command_ack', 'payload': {'status': 'rejected', 'detail': f'invalid json payload: {exc}'}}, ensure_ascii=False))
                    continue
                if not isinstance(payload, dict):
                    await ws.send_str(json.dumps({'type': 'command_ack', 'payload': {'status': 'rejected', 'detail': 'json payload must be an object'}}, ensure_ascii=False))
                    continue
                self.mirror.command_log.append({'source': 'ws', 'payload': payload, 'sessionRole': policy.role, 'sessionId': policy.session_id})
                command_type = str(payload.get('type', '') or '')
                if command_type in COMMAND_TYPES and not policy.write_enabled:
                    await ws.send_str(json.dumps(self._command_denied_payload(payload, policy), ensure_ascii=False))
                    continue
                dispatch = await self._dispatch_internal_command(payload)
                if not bool(dispatch.get('ok', False)):
                    await ws.send_str(json.dumps({'type': 'command_ack', 'payload': {'status': 'rejected', 'detail': str(dispatch.get('message', 'internal command dispatch failed'))}}, ensure_ascii=False))
        finally:
            self._local_clients.pop(ws, None)
        return ws
