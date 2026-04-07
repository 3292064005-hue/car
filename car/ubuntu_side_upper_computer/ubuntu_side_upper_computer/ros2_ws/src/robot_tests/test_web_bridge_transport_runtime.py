import asyncio

from robot_web_bridge.ws_transport import CONTROL_LANE, TELEMETRY_LANE, WebSocketHub, _ClientSession


class _Future:
    def add_done_callback(self, cb):
        self.cb = cb


class _Socket:
    def __init__(self) -> None:
        self.messages = []
        self.closed = False

    async def send(self, text: str) -> None:
        self.messages.append(text)

    async def close(self) -> None:
        self.closed = True


def test_schedule_send_aliases_broadcast(monkeypatch):
    calls = []
    test_loop = asyncio.new_event_loop()

    async def _noop(_message: str) -> None:
        return None

    hub = WebSocketHub(
        host='127.0.0.1',
        port=8765,
        ws_path='/ws',
        snapshot_provider=lambda: {},
        command_handler=_noop,
    )
    hub.loop = asyncio.new_event_loop()
    hub.clients = {object(): object()}

    async def _fake_broadcast_text(text: str, *, event_type: str) -> None:
        calls.append((text, event_type))

    monkeypatch.setattr(hub, '_broadcast_text', _fake_broadcast_text)
    monkeypatch.setattr('robot_web_bridge.ws_transport.asyncio.run_coroutine_threadsafe', lambda coro, loop: (_ := loop, test_loop.run_until_complete(coro), _Future())[2])

    try:
        hub.schedule_send({'type': 'heartbeat'})
    finally:
        test_loop.close()

    assert calls and 'heartbeat' in calls[0][0]
    assert calls[0][1] == 'heartbeat'


def test_client_session_coalesces_telemetry_messages():
    async def _run() -> None:
        socket = _Socket()
        session = _ClientSession(socket, control_queue_size=4)
        await session.start()
        await session.enqueue(text='{"type":"vision_target","payload":{"seq":1}}', lane=TELEMETRY_LANE, event_type='vision_target')
        await session.enqueue(text='{"type":"vision_target","payload":{"seq":2}}', lane=TELEMETRY_LANE, event_type='vision_target')
        await session.enqueue(text='{"type":"command_ack"}', lane=CONTROL_LANE, event_type='command_ack')
        await asyncio.sleep(0.05)
        await session.close()
        assert socket.messages[0] == '{"type":"command_ack"}'
        assert any('"seq":2' in item for item in socket.messages)
        assert all('"seq":1' not in item for item in socket.messages)

    asyncio.run(_run())



def test_broadcast_queue_full_drops_client_and_reports() -> None:
    async def _run() -> None:
        reports = []

        async def _noop(_message: str) -> None:
            return None

        class _FullSession:
            async def enqueue(self, *, text: str, lane: str, event_type: str) -> None:
                raise RuntimeError('control outbound queue full')

            async def close(self) -> None:
                self.closed = True

        hub = WebSocketHub(
            host='127.0.0.1',
            port=8765,
            ws_path='/ws',
            snapshot_provider=lambda: {},
            command_handler=_noop,
            stats_callback=lambda kind, **payload: reports.append((kind, payload)),
        )
        websocket = object()
        hub.clients = {websocket: _FullSession()}

        await hub._broadcast_text('{"type":"command_ack"}', event_type='command_ack')

        assert websocket not in hub.clients
        assert reports[0][0] == 'queue_full'
        assert reports[-1][0] == 'client_dropped'

    asyncio.run(_run())


def test_remove_client_reports_cleanup_failure() -> None:
    async def _run() -> None:
        reports = []

        async def _noop(_message: str) -> None:
            return None

        class _BrokenSession:
            async def close(self) -> None:
                raise RuntimeError('close failed')

        hub = WebSocketHub(
            host='127.0.0.1',
            port=8765,
            ws_path='/ws',
            snapshot_provider=lambda: {},
            command_handler=_noop,
            stats_callback=lambda kind, **payload: reports.append((kind, payload)),
        )
        websocket = object()
        hub.clients = {websocket: _BrokenSession()}

        await hub._remove_client(websocket)

        assert websocket not in hub.clients
        assert reports == [('client_cleanup_failed', {'error': 'close failed'})]

    asyncio.run(_run())


def test_broadcast_reports_payload_budget_exceeded(monkeypatch) -> None:
    async def _run() -> None:
        reports = []

        async def _noop(_message: str) -> None:
            return None

        class _Session:
            async def enqueue(self, *, text: str, lane: str, event_type: str) -> None:
                self.last = (text, lane, event_type)

            async def close(self) -> None:
                return None

        hub = WebSocketHub(
            host='127.0.0.1',
            port=8765,
            ws_path='/ws',
            snapshot_provider=lambda: {},
            command_handler=_noop,
            stats_callback=lambda kind, **payload: reports.append((kind, payload)),
            telemetry_payload_budget_bytes=32,
        )
        websocket = object()
        loop = asyncio.get_running_loop()
        hub.loop = loop
        hub.clients = {websocket: _Session()}

        class _FutureDone:
            def add_done_callback(self, callback):
                callback(self)

            def result(self):
                return None

        monkeypatch.setattr('robot_web_bridge.ws_transport.asyncio.run_coroutine_threadsafe', lambda coro, _loop: (loop.create_task(coro), _FutureDone())[1])

        hub.broadcast({'type': 'vision_target', 'payload': {'blob': 'x' * 128}})
        await asyncio.sleep(0.05)

        assert any(kind == 'payload_budget_exceeded' for kind, _payload in reports)
        assert any(kind == 'payload_measured' for kind, _payload in reports)

    asyncio.run(_run())


def test_handler_initial_snapshot_reports_payload_measurement() -> None:
    async def _run() -> None:
        reports = []
        received = []

        async def _noop(_message: str) -> None:
            return None

        class _WebSocket:
            path = '/ws'

            async def send(self, text: str) -> None:
                received.append(text)

            async def close(self, code=None, reason=None) -> None:
                return None

            def __aiter__(self):
                async def _gen():
                    if False:
                        yield None
                    return
                return _gen()

        hub = WebSocketHub(
            host='127.0.0.1',
            port=8765,
            ws_path='/ws',
            snapshot_provider=lambda: {'type': 'snapshot', 'payload': {'blob': 'x' * 16}},
            command_handler=_noop,
            stats_callback=lambda kind, **payload: reports.append((kind, payload)),
        )
        websocket = _WebSocket()
        await hub._handler(websocket)
        assert received
        assert any(kind == 'payload_measured' and payload.get('event_type') == 'snapshot' for kind, payload in reports)

    asyncio.run(_run())
