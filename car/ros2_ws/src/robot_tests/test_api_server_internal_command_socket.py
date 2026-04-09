from __future__ import annotations

import asyncio
import json
from pathlib import Path

from robot_api_server.proxy_server import RobotApiProxyServer


async def _start_fake_socket(path: str, *, expected_token: str):
    registered = {'ok': False, 'leaseEpoch': 1}

    async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        raw = await reader.readline()
        payload = json.loads(raw.decode('utf-8'))
        assert payload['__internalCommandAuthToken'] == expected_token
        if payload['type'] == '__register_internal_client__':
            registered['ok'] = True
            writer.write(json.dumps({"ok": True, "registered": True, "leaseEpoch": registered['leaseEpoch']}).encode('utf-8') + b'\n')
        else:
            assert registered['ok'] is True
            assert payload['type'] == 'set_mode'
            assert payload['__internalCommandLeaseEpoch'] == registered['leaseEpoch']
            writer.write(json.dumps({"ok": True, "leaseEpoch": registered['leaseEpoch']}).encode('utf-8') + b'\n')
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    return await asyncio.start_unix_server(_handle, path=path)


def test_api_server_dispatches_commands_over_internal_socket(tmp_path: Path) -> None:
    socket_path = str(tmp_path / 'bridge_internal.sock')
    token = 'runtime-secret'

    async def _exercise() -> None:
        server = await _start_fake_socket(socket_path, expected_token=token)
        try:
            proxy = RobotApiProxyServer(
                upstream_url='ws://127.0.0.1:9000/ws',
                listen_host='127.0.0.1',
                listen_port=9100,
                internal_command_socket_path=socket_path,
                internal_command_auth_token=token,
            )
            await proxy._register_internal_command_client()
            result = await proxy._dispatch_internal_command({'type': 'set_mode', 'eventId': 'evt-1'})
            assert result['ok'] is True
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(_exercise())
