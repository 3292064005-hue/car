#!/usr/bin/env python3
"""Run an integrated live smoke test for mock_system + robot_web_bridge + frontend.

This script assumes the caller has already sourced ROS 2 Humble and the workspace
install setup, and that ``npm ci`` has been executed under ``robot_frontend``. It
launches the mock ROS graph, waits for expected nodes and the WebSocket endpoint,
then executes the Playwright live-bridge smoke suite against the real bridge.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

DEFAULT_EXPECTED_READY_TOPICS = [
    '/robot/web_bridge/ready',
]

DEFAULT_EXPECTED_NODES = [
    '/robot_bridge_transport',
    '/robot_bridge_protocol',
    '/robot_bridge_projection',
    '/robot_bridge_health',
    '/robot_control',
    '/robot_decision',
    '/robot_web_bridge',
]


class IntegratedSmokeError(RuntimeError):
    """Raised when the integrated smoke test cannot complete successfully."""


def _parse_graph_items(stdout: str) -> set[str]:
    return {line.strip() for line in stdout.splitlines() if line.strip()}


def _run_graph_command(*args: str, timeout_sec: float) -> set[str]:
    try:
        completed = subprocess.run(
            ['ros2', *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or repr(exc)
        raise IntegratedSmokeError(f"ros2 {' '.join(args)} failed: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise IntegratedSmokeError(f"ros2 {' '.join(args)} timed out after {timeout_sec:.1f}s") from exc
    return _parse_graph_items(completed.stdout)


def _poll_for_expected_nodes(
    *,
    process: subprocess.Popen[str],
    expected_nodes: set[str],
    deadline_monotonic: float,
    graph_timeout_sec: float,
) -> set[str]:
    last_nodes: set[str] = set()
    while time.monotonic() < deadline_monotonic:
        if process.poll() is not None:
            raise IntegratedSmokeError(f'launch exited early with code {process.returncode}')
        try:
            last_nodes = _run_graph_command('node', 'list', timeout_sec=graph_timeout_sec)
        except IntegratedSmokeError:
            time.sleep(1.0)
            continue
        if expected_nodes.issubset(last_nodes):
            return last_nodes
        time.sleep(1.0)
    missing = sorted(expected_nodes - last_nodes)
    raise IntegratedSmokeError(f'timed out waiting for ROS graph readiness; missing nodes={missing}')


def _poll_for_expected_topics(
    *,
    process: subprocess.Popen[str],
    expected_topics: set[str],
    deadline_monotonic: float,
    graph_timeout_sec: float,
) -> set[str]:
    """Poll ROS graph topics until all operator-ready topics are advertised.

    Args:
        process: Running launch process.
        expected_topics: Topic names that must exist before the operator path is
            treated as ready.
        deadline_monotonic: Absolute startup deadline.
        graph_timeout_sec: Timeout for one ``ros2 topic list`` invocation.

    Returns:
        Observed topic set containing all expected topics.

    Raises:
        IntegratedSmokeError: When the launch exits early or the deadline
            expires before all ready topics appear.
    """
    if not expected_topics:
        return set()
    last_topics: set[str] = set()
    while time.monotonic() < deadline_monotonic:
        if process.poll() is not None:
            raise IntegratedSmokeError(f'launch exited early with code {process.returncode}')
        try:
            last_topics = _run_graph_command('topic', 'list', timeout_sec=graph_timeout_sec)
        except IntegratedSmokeError:
            time.sleep(1.0)
            continue
        if expected_topics.issubset(last_topics):
            return last_topics
        time.sleep(1.0)
    missing = sorted(expected_topics - last_topics)
    raise IntegratedSmokeError(f'timed out waiting for operator-ready topics; missing topics={missing}')

def _wait_for_tcp(host: str, port: int, *, deadline_monotonic: float) -> None:
    last_error = ''
    while time.monotonic() < deadline_monotonic:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError as exc:
            last_error = str(exc)
            time.sleep(0.5)
    raise IntegratedSmokeError(f'timed out waiting for tcp://{host}:{port}: {last_error or "unavailable"}')


def _wait_for_websocket_listener(ws_url: str, *, deadline_monotonic: float) -> None:
    """Wait until the websocket endpoint completes one real handshake.

    Args:
        ws_url: Target websocket URL.
        deadline_monotonic: Absolute startup deadline.

    Returns:
        None.

    Raises:
        IntegratedSmokeError: When the handshake does not complete before the
            deadline or the ``websockets`` dependency is unavailable.
    """
    try:
        import websockets
    except Exception as exc:  # pragma: no cover - environment setup failure
        raise IntegratedSmokeError(f'websocket probe dependency unavailable: {exc}') from exc

    last_error = ''

    async def _probe_once() -> None:
        websocket = await websockets.connect(ws_url, open_timeout=1.0, close_timeout=1.0, max_size=2**20)
        try:
            await asyncio.wait_for(websocket.recv(), timeout=1.0)
        finally:
            await websocket.close()

    while time.monotonic() < deadline_monotonic:
        try:
            asyncio.run(_probe_once())
            return
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.5)
    raise IntegratedSmokeError(f'timed out waiting for websocket listener {ws_url}: {last_error or "unavailable"}')


def _tail_text(path: Path, *, lines: int = 120) -> str:
    try:
        content = path.read_text(encoding='utf-8', errors='replace').splitlines()
    except FileNotFoundError:
        return '<log missing>'
    return '\n'.join(content[-lines:])


def _terminate_process_group(process: subprocess.Popen[str], *, grace_sec: float) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGINT)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=grace_sec)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=max(2.0, grace_sec / 2.0))
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        pass


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run an integrated mock_system + web_bridge + frontend smoke test.')
    parser.add_argument('--launch-package', default='robot_bringup')
    parser.add_argument('--launch-file', default='mock_system.launch.py')
    parser.add_argument('--launch-arg', action='append', default=['enable_voice:=false', 'enable_vision:=false'])
    parser.add_argument('--expected-node', action='append', default=None)
    parser.add_argument('--expected-ready-topic', action='append', default=None)
    parser.add_argument('--startup-timeout-sec', type=float, default=45.0)
    parser.add_argument('--graph-command-timeout-sec', type=float, default=5.0)
    parser.add_argument('--shutdown-grace-sec', type=float, default=8.0)
    parser.add_argument('--bridge-host', default='127.0.0.1')
    parser.add_argument('--bridge-port', type=int, default=9001)
    parser.add_argument('--bridge-path', default='/ws')
    parser.add_argument('--frontend-command', default='npm --prefix robot_frontend run test:e2e:live')
    parser.add_argument('--log-file', default='/tmp/integrated_frontend_bridge_smoke_launch.log')
    parser.add_argument('--frontend-log-file', default='/tmp/integrated_frontend_bridge_smoke_frontend.log')
    parser.add_argument('--ros-domain-id', type=int, default=91)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    expected_nodes = set(args.expected_node or DEFAULT_EXPECTED_NODES)
    expected_ready_topics = set(args.expected_ready_topic or DEFAULT_EXPECTED_READY_TOPICS)
    launch_log_path = Path(args.log_file)
    frontend_log_path = Path(args.frontend_log_file)
    launch_log_path.parent.mkdir(parents=True, exist_ok=True)
    frontend_log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault('PYTHONUNBUFFERED', '1')
    env.setdefault('CI', '1')
    env.setdefault('PLAYWRIGHT_LIVE_BRIDGE', '1')
    env.setdefault('VITE_ENABLE_MOCK', 'false')
    env.setdefault('VITE_ROBOT_WS_URL', f'ws://{args.bridge_host}:{args.bridge_port}{args.bridge_path}')
    env['ROS_DOMAIN_ID'] = str(args.ros_domain_id)

    launch_cmd = ['ros2', 'launch', args.launch_package, args.launch_file, *args.launch_arg]
    print(f'[integrated-smoke] launch command: {" ".join(launch_cmd)}')
    print(f'[integrated-smoke] frontend command: {args.frontend_command}')
    print(f'[integrated-smoke] ROS_DOMAIN_ID={env["ROS_DOMAIN_ID"]}')

    launch_process: subprocess.Popen[str] | None = None
    try:
        with launch_log_path.open('w', encoding='utf-8') as launch_log:
            launch_process = subprocess.Popen(
                launch_cmd,
                stdout=launch_log,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                start_new_session=True,
            )
            deadline = time.monotonic() + args.startup_timeout_sec
            _poll_for_expected_nodes(
                process=launch_process,
                expected_nodes=expected_nodes,
                deadline_monotonic=deadline,
                graph_timeout_sec=args.graph_command_timeout_sec,
            )
            _poll_for_expected_topics(
                process=launch_process,
                expected_topics=expected_ready_topics,
                deadline_monotonic=deadline,
                graph_timeout_sec=args.graph_command_timeout_sec,
            )
            _wait_for_tcp(args.bridge_host, args.bridge_port, deadline_monotonic=deadline)
            _wait_for_websocket_listener(f'ws://{args.bridge_host}:{args.bridge_port}{args.bridge_path}', deadline_monotonic=deadline)

            frontend_cmd = shlex.split(args.frontend_command)
            with frontend_log_path.open('w', encoding='utf-8') as frontend_log:
                completed = subprocess.run(
                    frontend_cmd,
                    cwd=Path(__file__).resolve().parents[1],
                    stdout=frontend_log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    timeout=max(120.0, args.startup_timeout_sec * 2.0),
                )
            if completed.returncode != 0:
                raise IntegratedSmokeError(f'frontend command failed with code {completed.returncode}')
    except IntegratedSmokeError as exc:
        print(f'[integrated-smoke] ERROR: {exc}', file=sys.stderr)
        print('\n===== ROS launch log tail =====', file=sys.stderr)
        print(_tail_text(launch_log_path), file=sys.stderr)
        print('\n===== Frontend smoke log tail =====', file=sys.stderr)
        print(_tail_text(frontend_log_path), file=sys.stderr)
        return 1
    finally:
        if launch_process is not None:
            _terminate_process_group(launch_process, grace_sec=args.shutdown_grace_sec)

    print('[integrated-smoke] success: live web bridge and frontend smoke completed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
