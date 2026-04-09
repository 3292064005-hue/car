from __future__ import annotations

import asyncio
import json
from pathlib import Path

from robot_web_bridge.internal_command_socket import InternalCommandSocketServer


def test_internal_command_socket_requires_registration_and_peer_auth(tmp_path: Path) -> None:
    socket_path = str(tmp_path / 'internal.sock')
    seen: list[dict[str, object]] = []

    async def _handler(payload: dict[str, object]) -> None:
        seen.append(payload)

    async def _exercise() -> None:
        server = InternalCommandSocketServer(socket_path=socket_path, auth_token='secret-token', request_handler=_handler)
        server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(socket_path)
            writer.write(b'{"type":"set_mode"}\n')
            await writer.drain()
            response = json.loads((await reader.readline()).decode('utf-8'))
            assert response['ok'] is False
            writer.close()
            await writer.wait_closed()

            reader, writer = await asyncio.open_unix_connection(socket_path)
            writer.write(b'{"type":"__register_internal_client__","__internalCommandAuthToken":"secret-token"}\n')
            await writer.drain()
            response = json.loads((await reader.readline()).decode('utf-8'))
            assert response['ok'] is True
            lease_epoch = response['leaseEpoch']
            writer.close()
            await writer.wait_closed()

            reader, writer = await asyncio.open_unix_connection(socket_path)
            writer.write(
                json.dumps(
                    {
                        'type': 'set_mode',
                        'eventId': 'evt-1',
                        '__internalCommandAuthToken': 'secret-token',
                        '__internalCommandLeaseEpoch': lease_epoch,
                    }
                ).encode('utf-8')
                + b'\n'
            )
            await writer.drain()
            response = json.loads((await reader.readline()).decode('utf-8'))
            assert response['ok'] is True
            assert response['leaseEpoch'] == lease_epoch
            writer.close()
            await writer.wait_closed()
        finally:
            server.stop()

    asyncio.run(_exercise())
    assert seen == [{'type': 'set_mode', 'eventId': 'evt-1'}]
