#!/usr/bin/env python3
"""Run a live ROS 2 launch smoke test against the built workspace.

This script is intended for CI environments where the workspace has already been
built and the shell has sourced both ``/opt/ros/<distro>/setup.bash`` and the
workspace ``install/setup.bash``. It launches a minimal bringup profile, waits
for a set of expected ROS nodes to appear in the graph, and then shuts the
launch down cleanly.
"""

from __future__ import annotations

import argparse
import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

DEFAULT_EXPECTED_NODES = [
    '/robot_bridge_transport',
    '/robot_bridge_protocol',
    '/robot_bridge_projection',
    '/robot_bridge_health',
    '/robot_control',
    '/robot_decision',
]


class SmokeTestError(RuntimeError):
    """Raised when the live ROS launch smoke test fails."""


def _parse_graph_items(stdout: str) -> set[str]:
    """Parse ``ros2 node list`` / ``ros2 topic list`` output into a set.

    Args:
        stdout: Raw command stdout.

    Returns:
        A set of non-empty stripped lines.

    Raises:
        None.
    """

    return {line.strip() for line in stdout.splitlines() if line.strip()}


def _run_graph_command(*args: str, timeout_sec: float) -> set[str]:
    """Execute one ROS graph inspection command.

    Args:
        *args: Command-line arguments after the ``ros2`` executable.
        timeout_sec: Per-command timeout in seconds.

    Returns:
        Parsed graph items from stdout.

    Raises:
        SmokeTestError: If the command fails unexpectedly.
    """

    try:
        completed = subprocess.run(
            ['ros2', *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        detail = stderr or stdout or repr(exc)
        raise SmokeTestError(f"ros2 {' '.join(args)} failed: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SmokeTestError(f"ros2 {' '.join(args)} timed out after {timeout_sec:.1f}s") from exc
    return _parse_graph_items(completed.stdout)


def _tail_text(path: Path, *, lines: int = 120) -> str:
    """Return the tail of a text file for failure diagnostics.

    Args:
        path: File to inspect.
        lines: Number of lines to keep from the tail.

    Returns:
        Tail text or a placeholder message when the file is unavailable.

    Raises:
        None.
    """

    try:
        content = path.read_text(encoding='utf-8', errors='replace').splitlines()
    except FileNotFoundError:
        return '<launch log missing>'
    return '\n'.join(content[-lines:])


def _terminate_process_group(process: subprocess.Popen[str], *, grace_sec: float) -> None:
    """Terminate the launch process group gracefully, then forcefully if needed.

    Args:
        process: Launch subprocess created with ``start_new_session=True``.
        grace_sec: Grace period after SIGINT before escalating.

    Returns:
        None.

    Raises:
        None. Cleanup is best-effort.
    """

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


def _poll_for_expected_graph(
    *,
    process: subprocess.Popen[str],
    expected_nodes: set[str],
    expected_topics: set[str],
    deadline_monotonic: float,
    graph_timeout_sec: float,
) -> tuple[set[str], set[str]]:
    """Poll the live ROS graph until expected nodes/topics are visible.

    Args:
        process: Active ``ros2 launch`` subprocess.
        expected_nodes: Required node names.
        expected_topics: Required topic names.
        deadline_monotonic: Absolute monotonic deadline.
        graph_timeout_sec: Per-command timeout for ``ros2 node/topic list``.

    Returns:
        A tuple of the latest node set and topic set observed.

    Raises:
        SmokeTestError: If the launch exits early or the deadline expires.
    """

    last_nodes: set[str] = set()
    last_topics: set[str] = set()
    while time.monotonic() < deadline_monotonic:
        if process.poll() is not None:
            raise SmokeTestError(f'launch exited early with code {process.returncode}')
        try:
            last_nodes = _run_graph_command('node', 'list', timeout_sec=graph_timeout_sec)
            if expected_topics:
                last_topics = _run_graph_command('topic', 'list', timeout_sec=graph_timeout_sec)
        except SmokeTestError:
            time.sleep(1.0)
            continue
        nodes_ready = expected_nodes.issubset(last_nodes)
        topics_ready = expected_topics.issubset(last_topics)
        if nodes_ready and topics_ready:
            return last_nodes, last_topics
        time.sleep(1.0)
    raise SmokeTestError(
        'timed out waiting for live ROS graph; '
        f'missing nodes={sorted(expected_nodes - last_nodes)}; '
        f'missing topics={sorted(expected_topics - last_topics)}'
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the smoke runner."""

    parser = argparse.ArgumentParser(description='Run a live ROS 2 launch smoke test.')
    parser.add_argument('--launch-package', default='robot_bringup')
    parser.add_argument('--launch-file', default='minimal_system.launch.py')
    parser.add_argument('--launch-arg', action='append', default=[], help='Extra launch argument in key:=value form.')
    parser.add_argument('--expected-node', action='append', default=None, help='Expected ROS node name. Repeat for multiple values.')
    parser.add_argument('--expected-topic', action='append', default=[], help='Expected ROS topic name. Repeat for multiple values.')
    parser.add_argument('--startup-timeout-sec', type=float, default=30.0)
    parser.add_argument('--graph-command-timeout-sec', type=float, default=5.0)
    parser.add_argument('--shutdown-grace-sec', type=float, default=8.0)
    parser.add_argument('--log-file', default='/tmp/ros_launch_smoke.log')
    parser.add_argument('--ros-domain-id', type=int, default=90)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    """Run the smoke test.

    Args:
        argv: Optional argument override.

    Returns:
        Process exit code.

    Raises:
        None. Errors are converted into user-facing diagnostics.
    """

    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    expected_nodes = set(args.expected_node or DEFAULT_EXPECTED_NODES)
    expected_topics = set(args.expected_topic)
    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault('PYTHONUNBUFFERED', '1')
    env['ROS_DOMAIN_ID'] = str(args.ros_domain_id)
    env.setdefault('RCUTILS_COLORIZED_OUTPUT', '1')

    launch_cmd = ['ros2', 'launch', args.launch_package, args.launch_file, *args.launch_arg]
    print(f'[live-ros-smoke] launch command: {" ".join(launch_cmd)}')
    print(f'[live-ros-smoke] ROS_DOMAIN_ID={env["ROS_DOMAIN_ID"]}')
    print(f'[live-ros-smoke] log file: {log_path}')
    launch_log = log_path.open('w', encoding='utf-8')
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            launch_cmd,
            stdout=launch_log,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )
        deadline = time.monotonic() + args.startup_timeout_sec
        observed_nodes, observed_topics = _poll_for_expected_graph(
            process=process,
            expected_nodes=expected_nodes,
            expected_topics=expected_topics,
            deadline_monotonic=deadline,
            graph_timeout_sec=args.graph_command_timeout_sec,
        )
        print(f'[live-ros-smoke] observed nodes: {sorted(observed_nodes)}')
        if expected_topics:
            print(f'[live-ros-smoke] observed topics: {sorted(observed_topics)}')
        return 0
    except SmokeTestError as exc:
        print(f'[live-ros-smoke] FAILURE: {exc}', file=sys.stderr)
        print('[live-ros-smoke] launch log tail follows:', file=sys.stderr)
        print(_tail_text(log_path), file=sys.stderr)
        return 1
    finally:
        if process is not None:
            _terminate_process_group(process, grace_sec=args.shutdown_grace_sec)
            try:
                subprocess.run(['ros2', 'daemon', 'stop'], check=False, capture_output=True, text=True, timeout=5.0, env=env)
            except Exception:
                pass
        launch_log.close()


if __name__ == '__main__':
    sys.exit(main())
