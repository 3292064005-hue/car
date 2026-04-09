from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from inspect import signature
from typing import Any, Awaitable, Callable, Mapping
from urllib.parse import parse_qsl, urlsplit

import websockets

from robot_web_bridge.payload_budget import (
    CONTROL_EVENT_TYPES,
    DEFAULT_CONTROL_PAYLOAD_BUDGET_BYTES,
    DEFAULT_SNAPSHOT_PAYLOAD_BUDGET_BYTES,
    DEFAULT_TELEMETRY_PAYLOAD_BUDGET_BYTES,
    resolve_payload_budget,
)

TELEMETRY_LANE = 'telemetry'
CONTROL_LANE = 'control'
DEFAULT_CONTROL_QUEUE_SIZE = 64
DEFAULT_STARTUP_TIMEOUT_SEC = 5.0
_MAX_SNAPSHOT_LOG_ITEMS = 6
_MAX_SNAPSHOT_COMMAND_AUDIT_ITEMS = 6
_MAX_SNAPSHOT_COMMAND_TIMELINE_ITEMS = 12
_MAX_SNAPSHOT_QR_ITEMS = 4
_MAX_SNAPSHOT_VOICE_ITEMS = 4


@dataclass(slots=True)
class _ClientSession:
    """Per-client outbound state with bounded control queue and coalesced telemetry."""

    websocket: Any
    policy: Mapping[str, Any] | None = None
    control_queue_size: int = DEFAULT_CONTROL_QUEUE_SIZE
    control_queue: asyncio.Queue[str] = field(init=False)
    telemetry_latest: dict[str, str] = field(default_factory=dict)
    telemetry_event: asyncio.Event = field(default_factory=asyncio.Event)
    sender_task: asyncio.Task[Any] | None = None

    def __post_init__(self) -> None:
        self.control_queue = asyncio.Queue(maxsize=self.control_queue_size)

    async def start(self) -> None:
        self.sender_task = asyncio.create_task(self._sender_loop())

    async def close(self) -> None:
        if self.sender_task is not None:
            self.sender_task.cancel()
            try:
                await self.sender_task
            except asyncio.CancelledError:
                pass
            self.sender_task = None
        await self.websocket.close()

    async def enqueue(self, *, text: str, lane: str, event_type: str) -> None:
        if lane == TELEMETRY_LANE:
            self.telemetry_latest[event_type] = text
            self.telemetry_event.set()
            return
        if self.control_queue.full():
            raise RuntimeError('control outbound queue full')
        await self.control_queue.put(text)

    async def _sender_loop(self) -> None:
        while True:
            if not self.control_queue.empty():
                text = await self.control_queue.get()
                await self.websocket.send(text)
                continue
            if self.telemetry_latest:
                pending = list(self.telemetry_latest.values())
                self.telemetry_latest.clear()
                self.telemetry_event.clear()
                for text in pending:
                    await self.websocket.send(text)
                continue
            control_task = asyncio.create_task(self.control_queue.get())
            telemetry_task = asyncio.create_task(self.telemetry_event.wait())
            try:
                done, pending = await asyncio.wait({control_task, telemetry_task}, return_when=asyncio.FIRST_COMPLETED)
            except asyncio.CancelledError:
                for task in (control_task, telemetry_task):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(control_task, telemetry_task, return_exceptions=True)
                raise
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            if control_task in done and not control_task.cancelled():
                await self.websocket.send(control_task.result())
                continue
            if telemetry_task in done and not telemetry_task.cancelled():
                continue


class WebSocketHub:
    """Background websocket hub used by the web bridge."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        ws_path: str,
        snapshot_provider: Callable[[], dict[str, Any]],
        command_handler: Callable[[str, Mapping[str, Any] | None], Awaitable[None]] | Callable[[str], Awaitable[None]],
        stats_callback: Callable[[str], None] | Callable[..., None] | None = None,
        session_policy_resolver: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
        outbound_event_transform: Callable[[dict[str, Any], Mapping[str, Any] | None], dict[str, Any]] | None = None,
        telemetry_payload_budget_bytes: int = DEFAULT_TELEMETRY_PAYLOAD_BUDGET_BYTES,
        control_payload_budget_bytes: int = DEFAULT_CONTROL_PAYLOAD_BUDGET_BYTES,
        snapshot_payload_budget_bytes: int = DEFAULT_SNAPSHOT_PAYLOAD_BUDGET_BYTES,
    ) -> None:
        self.host = host
        self.port = port
        self.ws_path = ws_path
        self.snapshot_provider = snapshot_provider
        self.command_handler = command_handler
        self.stats_callback = stats_callback
        self.session_policy_resolver = session_policy_resolver
        self.outbound_event_transform = outbound_event_transform
        self.telemetry_payload_budget_bytes = int(telemetry_payload_budget_bytes)
        self.control_payload_budget_bytes = int(control_payload_budget_bytes)
        self.snapshot_payload_budget_bytes = int(snapshot_payload_budget_bytes)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.clients: dict[Any, _ClientSession] = {}
        self.server: Any | None = None
        self.bound_host: str = str(host)
        self.bound_port: int = int(port)
        self._startup_future: Future[dict[str, Any]] | None = None
        self._thread_lock = threading.Lock()


    @staticmethod
    def _remote_address_payload(websocket: Any) -> dict[str, Any]:
        remote = getattr(websocket, 'remote_address', None)
        if isinstance(remote, tuple):
            host = str(remote[0]) if len(remote) >= 1 and remote[0] is not None else ''
            port = int(remote[1]) if len(remote) >= 2 and isinstance(remote[1], int) else None
            return {
                'host': host,
                'port': port,
                'raw': list(remote),
            }
        if isinstance(remote, str):
            return {
                'host': remote,
                'port': None,
                'raw': remote,
            }
        return {
            'host': '',
            'port': None,
            'raw': remote,
        }

    def _request_metadata_from_connection(self, path: str, websocket: Any | None = None) -> dict[str, Any]:
        parsed = urlsplit(path or '')
        remote_address = self._remote_address_payload(websocket) if websocket is not None else {
            'host': '',
            'port': None,
            'raw': None,
        }
        return {
            'path': parsed.path or '',
            'query': dict(parse_qsl(parsed.query, keep_blank_values=True)),
            'remote_address': remote_address,
        }

    def _resolve_client_policy(self, path: str, websocket: Any | None = None) -> Mapping[str, Any] | None:
        metadata = self._request_metadata_from_connection(path, websocket)
        if self.session_policy_resolver is None:
            return metadata
        try:
            return self.session_policy_resolver(metadata)
        except Exception as exc:
            self._report('session_policy_resolution_failed', error=str(exc))
            return metadata

    def _transform_outbound_event(self, envelope: dict[str, Any], policy: Mapping[str, Any] | None) -> dict[str, Any]:
        if self.outbound_event_transform is None:
            return dict(envelope)
        try:
            return self.outbound_event_transform(dict(envelope), policy)
        except Exception as exc:
            self._report('outbound_event_transform_failed', error=str(exc))
            return dict(envelope)

    async def _dispatch_command(self, raw: str, policy: Mapping[str, Any] | None) -> None:
        try:
            param_count = len(signature(self.command_handler).parameters)
        except Exception:
            param_count = 1
        if param_count <= 1:
            await self.command_handler(raw)
            return
        await self.command_handler(raw, policy)

    def start(self, *, timeout_sec: float = DEFAULT_STARTUP_TIMEOUT_SEC) -> dict[str, Any]:
        """Start the websocket listener and wait for the bind handshake.

        Args:
            timeout_sec: Maximum wait for the listener thread to bind the
                websocket endpoint and publish startup metadata.

        Returns:
            Listener metadata containing host, port, and websocket path.

        Raises:
            RuntimeError: When the listener cannot start or does not report a
                successful bind before ``timeout_sec`` expires.
        """
        with self._thread_lock:
            if self.thread is not None and self.thread.is_alive():
                return {
                    'host': self.bound_host,
                    'port': int(self.bound_port),
                    'ws_path': self.ws_path,
                }
            self._startup_future = Future()
            self.thread = threading.Thread(target=self._thread_main, daemon=True)
            self.thread.start()
        try:
            startup = self._startup_future.result(timeout=max(0.1, float(timeout_sec)))
        except Exception as exc:
            self.stop()
            raise RuntimeError(f'websocket listener failed to start: {exc}') from exc
        return startup

    def stop(self) -> None:
        loop = self.loop
        thread = self.thread
        if loop is not None and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._shutdown_async(), loop)
            try:
                future.result(timeout=3.0)
            except Exception as exc:
                self._report('shutdown_failed', error=str(exc))
                try:
                    loop.call_soon_threadsafe(loop.stop)
                except RuntimeError:
                    pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)

    def broadcast(self, envelope: dict[str, Any]) -> None:
        if self.loop is None or not self.clients:
            return
        event_type, text = self._prepare_envelope(envelope)
        future = asyncio.run_coroutine_threadsafe(self._broadcast_text(text, event_type=event_type), self.loop)
        future.add_done_callback(self._consume_future_exception)

    def schedule_send(self, envelope: dict[str, Any]) -> None:
        self.broadcast(envelope)

    def _prepare_envelope(self, envelope: dict[str, Any]) -> tuple[str, str]:
        event_type = str(envelope.get('type', '') or '')
        lane, budget_bytes = resolve_payload_budget(
            event_type,
            telemetry_budget_bytes=self.telemetry_payload_budget_bytes,
            control_budget_bytes=self.control_payload_budget_bytes,
            snapshot_budget_bytes=self.snapshot_payload_budget_bytes,
        )
        prepared_envelope = dict(envelope)
        text, payload_bytes = self._serialize_envelope(prepared_envelope)
        if payload_bytes > budget_bytes:
            self._report(
                'payload_budget_exceeded',
                event_type=event_type or 'telemetry',
                lane=lane,
                payload_bytes=payload_bytes,
                budget_bytes=budget_bytes,
            )
            prepared_envelope, text, payload_bytes = self._apply_payload_budget_policy(
                envelope=prepared_envelope,
                event_type=event_type,
                lane=lane,
                budget_bytes=budget_bytes,
                original_payload_bytes=payload_bytes,
            )
        self._report(
            'payload_measured',
            event_type=event_type or 'telemetry',
            lane=lane,
            payload_bytes=payload_bytes,
            budget_bytes=budget_bytes,
        )
        return event_type, text

    def _apply_payload_budget_policy(
        self,
        *,
        envelope: dict[str, Any],
        event_type: str,
        lane: str,
        budget_bytes: int,
        original_payload_bytes: int,
    ) -> tuple[dict[str, Any], str, int]:
        if event_type == 'snapshot':
            compact = self._compact_snapshot_envelope(envelope)
            compact_text, compact_bytes = self._serialize_envelope(compact)
            if compact_bytes <= budget_bytes:
                self._report(
                    'payload_degraded',
                    event_type=event_type or 'snapshot',
                    lane=lane,
                    payload_bytes=compact_bytes,
                    budget_bytes=budget_bytes,
                    original_payload_bytes=original_payload_bytes,
                    policy='snapshot_compaction',
                )
                return compact, compact_text, compact_bytes
        if lane == TELEMETRY_LANE:
            degraded = self._compact_telemetry_envelope(envelope)
            degraded_text, degraded_bytes = self._serialize_envelope(degraded)
            if degraded_bytes <= budget_bytes:
                self._report(
                    'payload_degraded',
                    event_type=event_type or 'telemetry',
                    lane=lane,
                    payload_bytes=degraded_bytes,
                    budget_bytes=budget_bytes,
                    original_payload_bytes=original_payload_bytes,
                    policy='telemetry_compaction',
                )
                return degraded, degraded_text, degraded_bytes
        original_text, original_bytes = self._serialize_envelope(envelope)
        return envelope, original_text, original_bytes

    def _serialize_envelope(self, envelope: Mapping[str, Any]) -> tuple[str, int]:
        text = json.dumps(dict(envelope), ensure_ascii=False)
        return text, len(text.encode('utf-8'))

    def _compact_snapshot_envelope(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        compact = dict(envelope)
        payload = dict(compact.get('payload', {})) if isinstance(compact.get('payload'), Mapping) else {}
        if isinstance(payload.get('logs'), list):
            payload['logs'] = list(payload['logs'])[-_MAX_SNAPSHOT_LOG_ITEMS:]
        if isinstance(payload.get('commandAudit'), list):
            payload['commandAudit'] = list(payload['commandAudit'])[-_MAX_SNAPSHOT_COMMAND_AUDIT_ITEMS:]
        if isinstance(payload.get('commandTimeline'), list):
            payload['commandTimeline'] = list(payload['commandTimeline'])[-_MAX_SNAPSHOT_COMMAND_TIMELINE_ITEMS:]
        vision = dict(payload.get('vision', {})) if isinstance(payload.get('vision'), Mapping) else None
        if vision is not None and isinstance(vision.get('qrcodeHistory'), list):
            vision['qrcodeHistory'] = list(vision['qrcodeHistory'])[-_MAX_SNAPSHOT_QR_ITEMS:]
            payload['vision'] = vision
        voice = dict(payload.get('voice', {})) if isinstance(payload.get('voice'), Mapping) else None
        if voice is not None and isinstance(voice.get('recentCommands'), list):
            voice['recentCommands'] = list(voice['recentCommands'])[-_MAX_SNAPSHOT_VOICE_ITEMS:]
            payload['voice'] = voice
        transport = dict(payload.get('transport', {})) if isinstance(payload.get('transport'), Mapping) else None
        if transport is not None:
            transport.pop('payload_bytes_by_lane', None)
            transport.pop('last_transport_observation', None)
            payload['transport'] = transport
        payload['budgetDegraded'] = True
        payload['budgetPolicy'] = 'snapshot_compaction'
        compact['payload'] = payload
        return compact

    def _compact_telemetry_envelope(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        compact = dict(envelope)
        payload = compact.get('payload', {})
        payload_mapping = dict(payload) if isinstance(payload, Mapping) else {}
        compact['payload'] = {
            'degraded': True,
            'reason': 'payload_budget_exceeded',
            'originalPayloadKeys': sorted(payload_mapping.keys())[:8],
            'lastUpdateAt': payload_mapping.get('lastUpdateAt'),
        }
        return compact

    def _report(self, kind: str, **payload: Any) -> None:
        if self.stats_callback is None:
            return
        try:
            self.stats_callback(kind, **payload)
        except TypeError:
            self.stats_callback(kind)

    def _consume_future_exception(self, future: Future[Any]) -> None:
        try:
            future.result()
        except Exception as exc:
            self._report('future_exception', error=str(exc))

    async def _broadcast_text(self, text: str, *, event_type: str) -> None:
        stale: list[Any] = []
        lane = CONTROL_LANE if event_type in CONTROL_EVENT_TYPES else TELEMETRY_LANE
        try:
            envelope = json.loads(text)
        except Exception:
            envelope = None
        for websocket, session in tuple(self.clients.items()):
            outbound_text = text
            outbound_event_type = event_type or 'telemetry'
            if isinstance(envelope, dict):
                transformed = self._transform_outbound_event(envelope, getattr(session, 'policy', None))
                outbound_event_type, outbound_text = self._prepare_envelope(transformed)
            try:
                await session.enqueue(text=outbound_text, lane=lane, event_type=outbound_event_type or 'telemetry')
            except Exception as exc:
                self._report('queue_full' if 'queue full' in str(exc) else 'enqueue_failed', event_type=outbound_event_type or 'telemetry', error=str(exc))
                stale.append(websocket)
        for websocket in stale:
            await self._remove_client(websocket)

    async def _remove_client(self, websocket: Any) -> None:
        session = self.clients.pop(websocket, None)
        if session is None:
            return
        try:
            await session.close()
        except Exception as exc:
            self._report('client_cleanup_failed', error=str(exc))
            return
        self._report('client_dropped')

    async def _shutdown_async(self) -> None:
        for websocket in tuple(self.clients):
            await self._remove_client(websocket)
        loop = asyncio.get_running_loop()
        loop.stop()

    async def _start_server_async(self) -> Any:
        return await websockets.serve(
            self._handler_entry,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=20,
            max_size=2**20,
        )

    def _listener_details(self, server: Any) -> dict[str, Any]:
        listening_host = str(self.host)
        listening_port = int(self.port)
        sockets = tuple(getattr(server, 'sockets', ()) or ())
        if sockets:
            sockname = sockets[0].getsockname()
            if isinstance(sockname, tuple):
                if len(sockname) >= 1 and sockname[0]:
                    listening_host = str(sockname[0])
                if len(sockname) >= 2:
                    listening_port = int(sockname[1])
        self.bound_host = listening_host
        self.bound_port = listening_port
        return {
            'host': listening_host,
            'port': listening_port,
            'ws_path': self.ws_path,
        }

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop = loop
        server = None
        startup_future = self._startup_future
        try:
            server = loop.run_until_complete(self._start_server_async())
            self.server = server
            startup = self._listener_details(server)
            if startup_future is not None and not startup_future.done():
                startup_future.set_result(startup)
            self._report('listener_ready', **startup)
            loop.run_forever()
        except Exception as exc:
            if startup_future is not None and not startup_future.done():
                startup_future.set_exception(exc)
            self._report('listener_failed', error=str(exc), host=str(self.host), port=int(self.port), ws_path=self.ws_path)
        finally:
            try:
                for websocket in tuple(self.clients):
                    loop.run_until_complete(self._remove_client(websocket))
                if server is not None:
                    server.close()
                    loop.run_until_complete(server.wait_closed())
            finally:
                self.server = None
                self.loop = None
                self.clients.clear()
                if server is not None:
                    self._report('listener_stopped', host=self.bound_host, port=int(self.bound_port), ws_path=self.ws_path)
                loop.close()
                asyncio.set_event_loop(None)

    def _resolve_request_path(self, websocket: Any, explicit_path: str | None = None) -> str:
        if explicit_path:
            return str(explicit_path)
        request = getattr(websocket, 'request', None)
        request_path = getattr(request, 'path', None)
        if request_path:
            return str(request_path)
        path = getattr(websocket, 'path', None)
        if path:
            return str(path)
        return self.ws_path

    async def _handler_entry(self, websocket: Any, *args: Any) -> None:
        explicit_path = str(args[0]) if args else None
        path = self._resolve_request_path(websocket, explicit_path=explicit_path)
        resolved_path = self._request_metadata_from_connection(path).get('path', '') or ''
        if resolved_path != self.ws_path:
            await websocket.close(code=1008, reason=f'unsupported path: {resolved_path or path}')
            return
        policy = self._resolve_client_policy(path, websocket)
        session = _ClientSession(websocket, policy=policy)
        self._report('client_connected')
        self.clients[websocket] = session
        await session.start()
        snapshot_envelope = self._transform_outbound_event(self.snapshot_provider(), session.policy)
        _snapshot_event_type, snapshot_text = self._prepare_envelope(snapshot_envelope)
        await websocket.send(snapshot_text)
        try:
            async for message in websocket:
                await self._dispatch_command(message, session.policy)
        finally:
            await self._remove_client(websocket)

    async def _handler(self, websocket: Any) -> None:
        """Backward-compatible handler entry used by lightweight tests."""
        await self._handler_entry(websocket)
