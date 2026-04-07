from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

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


@dataclass(slots=True)
class _ClientSession:
    """Per-client outbound state with bounded control queue and coalesced telemetry."""

    websocket: Any
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
            done, pending = await asyncio.wait({control_task, telemetry_task}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
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
        command_handler: Callable[[str], Awaitable[None]],
        stats_callback: Callable[[str], None] | Callable[..., None] | None = None,
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
        self.telemetry_payload_budget_bytes = int(telemetry_payload_budget_bytes)
        self.control_payload_budget_bytes = int(control_payload_budget_bytes)
        self.snapshot_payload_budget_bytes = int(snapshot_payload_budget_bytes)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.clients: dict[Any, _ClientSession] = {}

    def start(self) -> None:
        self.thread = threading.Thread(target=self._thread_main, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.loop is not None and self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._shutdown_async(), self.loop)
            try:
                future.result(timeout=3.0)
            except Exception as exc:
                self._report('shutdown_failed', error=str(exc))
                self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=3.0)

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
        text = json.dumps(envelope, ensure_ascii=False)
        payload_bytes = len(text.encode('utf-8'))
        lane, budget_bytes = resolve_payload_budget(
            event_type,
            telemetry_budget_bytes=self.telemetry_payload_budget_bytes,
            control_budget_bytes=self.control_payload_budget_bytes,
            snapshot_budget_bytes=self.snapshot_payload_budget_bytes,
        )
        if payload_bytes > budget_bytes:
            self._report(
                'payload_budget_exceeded',
                event_type=event_type or 'telemetry',
                lane=lane,
                payload_bytes=payload_bytes,
                budget_bytes=budget_bytes,
            )
        self._report(
            'payload_measured',
            event_type=event_type or 'telemetry',
            lane=lane,
            payload_bytes=payload_bytes,
            budget_bytes=budget_bytes,
        )
        return event_type, text

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
        for websocket, session in tuple(self.clients.items()):
            try:
                await session.enqueue(text=text, lane=lane, event_type=event_type or 'telemetry')
            except Exception as exc:
                self._report('queue_full' if 'queue full' in str(exc) else 'enqueue_failed', event_type=event_type or 'telemetry', error=str(exc))
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

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop = loop
        start_server = websockets.serve(self._handler, self.host, self.port, ping_interval=20, ping_timeout=20, max_size=2**20)
        server = loop.run_until_complete(start_server)
        try:
            loop.run_forever()
        finally:
            for websocket in tuple(self.clients):
                loop.run_until_complete(self._remove_client(websocket))
            server.close()
            loop.run_until_complete(server.wait_closed())
            loop.close()

    async def _handler(self, websocket: Any) -> None:
        path = getattr(websocket, 'path', self.ws_path)
        if path != self.ws_path:
            await websocket.close(code=1008, reason=f'unsupported path: {path}')
            return
        session = _ClientSession(websocket)
        self._report('client_connected')
        self.clients[websocket] = session
        await session.start()
        _snapshot_event_type, snapshot_text = self._prepare_envelope(self.snapshot_provider())
        await websocket.send(snapshot_text)
        try:
            async for message in websocket:
                await self.command_handler(message)
        finally:
            await self._remove_client(websocket)
