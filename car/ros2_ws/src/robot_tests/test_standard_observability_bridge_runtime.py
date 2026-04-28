from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import websockets

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robot_web_bridge.standard_observability_bridge_launcher import build_launch_command
from robot_web_bridge.standard_observability_contract import resolve_standard_observability_bridge_contract


class _MockObserverSurface:
    def __init__(self, *, host: str, port: int, ws_path: str, messages: list[str]) -> None:
        self.host = host
        self.port = int(port)
        self.ws_path = ws_path
        self.messages = messages
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.ready = threading.Event()
        self.stop_requested = threading.Event()

    async def _handler(self, websocket: Any, *args: Any) -> None:
        request = getattr(websocket, 'request', None)
        path = str(getattr(request, 'path', '') or (args[0] if args else '') or self.ws_path)
        assert path.split('?', 1)[0] == self.ws_path
        for raw in self.messages:
            await websocket.send(raw)
            await asyncio.sleep(0.05)
        while not self.stop_requested.is_set():
            await asyncio.sleep(0.05)

    def start(self) -> None:
        def _run() -> None:
            loop = asyncio.new_event_loop()
            self.loop = loop
            asyncio.set_event_loop(loop)
            server = loop.run_until_complete(websockets.serve(self._handler, self.host, self.port, ping_interval=20, ping_timeout=20))
            self.ready.set()
            try:
                loop.run_until_complete(self._wait_for_stop())
            finally:
                server.close()
                loop.run_until_complete(server.wait_closed())
                loop.close()
                asyncio.set_event_loop(None)

        self.thread = threading.Thread(target=_run, daemon=True)
        self.thread.start()
        assert self.ready.wait(timeout=5.0)

    async def _wait_for_stop(self) -> None:
        while not self.stop_requested.is_set():
            await asyncio.sleep(0.05)

    def stop(self) -> None:
        self.stop_requested.set()
        if self.thread is not None:
            self.thread.join(timeout=5.0)


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def test_bridge_contract_resolves_from_config_defaults() -> None:
    contract = resolve_standard_observability_bridge_contract(ROOT / 'ros2_ws' / 'src' / 'robot_bringup' / 'config')
    assert contract['enabled'] is False
    assert contract['bridgeFamily'] == 'repo_readonly_websocket'
    assert contract['writeIngressAllowed'] is False
    assert contract['protocol'] == 'contract_only'


def test_bridge_launcher_builds_repo_readonly_runtime_command() -> None:
    command = build_launch_command(
        bridge_family='repo_readonly_websocket',
        listen_host='127.0.0.1',
        port=8765,
        ws_path='/observability',
        command_override=(),
        readonly_topics=('/robot/bridge/summary', '/robot/runtime/supervision'),
        upstream_url='ws://127.0.0.1:9001/ws',
    )
    joined = ' '.join(command)
    assert 'robot_web_bridge.standard_observability_bridge_runtime' in joined
    assert '--readonly-topic /robot/bridge/summary' in joined
    assert '--upstream-url ws://127.0.0.1:9001/ws' in joined


def test_bridge_launcher_rejects_non_repo_runtime_family() -> None:
    try:
        build_launch_command(
            bridge_family='foxglove_bridge',
            listen_host='127.0.0.1',
            port=8765,
            ws_path='/observability',
            command_override=(),
            readonly_topics=(),
            upstream_url='ws://127.0.0.1:9001/ws',
        )
    except ValueError as exc:
        assert 'policy-blocked' in str(exc)
    else:
        raise AssertionError('expected policy-blocked ValueError')


def test_bridge_runtime_proxies_readonly_topics_and_rejects_write_like_ops() -> None:
    upstream_port = _free_port()
    bridge_port = _free_port()
    ws_path = '/observability'
    upstream_url = f'ws://127.0.0.1:{upstream_port}/ws'
    snapshot = {
        'type': 'snapshot',
        'payload': {
            'connection': {
                'bridgeConnected': True,
                'transportLabel': 'connected',
                'gatewayReady': True,
                'operatorSurfaceReady': True,
                'lastHeartbeatAt': '2026-04-19T12:00:00Z',
            },
            'motion': {'mode': 'AUTO', 'linearVelocity': 0.3, 'angularVelocity': 0.1, 'lastUpdateAt': '2026-04-19T12:00:01Z'},
            'power': {'lowPowerWarning': False, 'lastUpdateAt': '2026-04-19T12:00:02Z'},
            'task': {'patrolStatus': 'running', 'currentWaypoint': 'P1', 'progress': 0.5, 'actionName': 'patrol', 'actionPhase': 'running'},
            'fault': {'level': 'info', 'safeStopActive': False, 'estopActive': False, 'message': None, 'lastUpdateAt': '2026-04-19T12:00:03Z'},
            'reports': {
                'controlSummary': {'kind': 'control_summary', 'status': 'drive', 'details': {'winner': 'nav'}, 'topic': '/robot/control/summary'},
                'navigationStatus': {'kind': 'navigation_status', 'status': 'running', 'details': {'routeName': 'patrol'}, 'topic': '/robot/navigation/status'},
                'runtimeSupervision': {'kind': 'runtime_supervision', 'status': 'ready', 'details': {'reasons': ['ready']}, 'topic': '/robot/runtime/supervision'},
            },
        },
    }
    mode_state = {'type': 'mode_state', 'payload': {'mode': 'MANUAL', 'commandSource': 'teleop', 'lastUpdateAt': '2026-04-19T12:00:04Z'}}
    observer = _MockObserverSurface(host='127.0.0.1', port=upstream_port, ws_path='/ws', messages=[json.dumps(snapshot, ensure_ascii=False), json.dumps(mode_state, ensure_ascii=False)])
    observer.start()
    runtime = ROOT / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'standard_observability_bridge_runtime.py'
    env = dict(os.environ)
    env['PYTHONPATH'] = f"{ROOT / 'ros2_ws' / 'src'}:{env.get('PYTHONPATH', '')}".rstrip(':')
    process = subprocess.Popen(
        [
            sys.executable,
            str(runtime),
            '--listen-host', '127.0.0.1',
            '--port', str(bridge_port),
            '--ws-path', ws_path,
            '--upstream-url', upstream_url,
            '--readonly-topic', '/robot/bridge/summary',
            '--readonly-topic', '/robot/decision/summary',
            '--readonly-topic', '/robot/control/summary',
            '--readonly-topic', '/robot/navigation/status',
            '--readonly-topic', '/robot/runtime/supervision',
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.time() + 8.0
        connected = False
        while time.time() < deadline and not connected:
            try:
                asyncio.run(_probe_runtime(bridge_port, ws_path))
                connected = True
            except Exception:
                time.sleep(0.1)
        failure_detail = 'runtime did not start'
        if not connected and process.poll() is not None and process.stderr is not None:
            failure_detail = process.stderr.read() or failure_detail
        assert connected, failure_detail
    finally:
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
        observer.stop()


async def _probe_runtime(port: int, ws_path: str) -> None:
    uri = f'ws://127.0.0.1:{port}{ws_path}'
    async with websockets.connect(uri, ping_interval=20, ping_timeout=20, max_size=2**20) as ws:
        info = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
        assert info['op'] == 'bridge_info'
        assert info['readonly'] is True
        assert info['authorityBoundary'] == '9100_api_facade_only'
        seen_topics: set[str] = set()
        while len(seen_topics) < 5:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
            assert message['op'] == 'publish'
            seen_topics.add(str(message['topic']))
        assert '/robot/runtime/supervision' in seen_topics
        await ws.send(json.dumps({'op': 'publish', 'topic': '/robot/control/summary', 'msg': {'force': 'write'}}))
        error = await _recv_until_op(ws, 'error')
        assert error['code'] == 'READONLY_BRIDGE_UNSUPPORTED_OP'
        await ws.send(json.dumps({'op': 'unsubscribe', 'topics': ['/robot/decision/summary']}))
        unsubscribed = await _recv_until_op(ws, 'unsubscribed')
        assert unsubscribed['topics'] == ['/robot/decision/summary']
        await ws.send(json.dumps({'op': 'ping'}))
        pong = await _recv_until_op(ws, 'pong')
        assert pong['op'] == 'pong'


async def _recv_until_op(ws: Any, op: str) -> dict[str, Any]:
    deadline = time.time() + 3.0
    while time.time() < deadline:
        message = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
        if message.get('op') == op:
            return message
    raise AssertionError(f'expected op {op!r}')
