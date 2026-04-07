from __future__ import annotations

"""ROS startup barrier used by bringup launch sequencing.

The barrier intentionally uses the ``ros2`` CLI instead of in-process graph APIs so it
can run as a short-lived helper process from launch without importing the running
system's node implementations. Readiness can require a combination of ROS graph
presence (nodes/topics) and active service/action endpoints when requested by the
launch profile.
"""

import argparse
import subprocess
import sys
import time
from typing import Iterable


DEFAULT_TIMEOUT_SEC = 20.0
DEFAULT_POLL_INTERVAL_SEC = 0.25


def _normalize_entries(values: Iterable[str]) -> set[str]:
    normalized: set[str] = set()
    for item in values:
        raw = str(item or '').strip()
        if not raw:
            continue
        normalized.add(raw if raw.startswith('/') else f'/{raw}')
    return normalized


def _normalize_groups(values: Iterable[str]) -> list[set[str]]:
    groups: list[set[str]] = []
    for item in values:
        raw = str(item or '').strip()
        if not raw:
            continue
        members = [part.strip() for part in raw.split(',') if part.strip()]
        group = _normalize_entries(members)
        if group:
            groups.append(group)
    return groups


def _cli_listing(*args: str) -> set[str]:
    completed = subprocess.run(args, check=True, capture_output=True, text=True, timeout=10.0)
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def _groups_ready(expected_groups: list[set[str]], observed_nodes: set[str]) -> tuple[bool, list[str]]:
    if not expected_groups:
        return True, []
    for group in expected_groups:
        if group.issubset(observed_nodes):
            return True, []
    missing_summary = [','.join(sorted(group - observed_nodes)) for group in expected_groups]
    return False, missing_summary


def wait_for_ros_graph(
    *,
    label: str,
    expected_nodes: Iterable[str],
    expected_topics: Iterable[str],
    expected_services: Iterable[str],
    expected_actions: Iterable[str],
    expected_node_groups: Iterable[str],
    timeout_sec: float,
    poll_interval_sec: float,
) -> int:
    expected_node_set = _normalize_entries(expected_nodes)
    expected_topic_set = _normalize_entries(expected_topics)
    expected_service_set = _normalize_entries(expected_services)
    expected_action_set = _normalize_entries(expected_actions)
    expected_node_group_sets = _normalize_groups(expected_node_groups)
    deadline = time.monotonic() + max(0.1, float(timeout_sec))
    last_nodes: set[str] = set()
    last_topics: set[str] = set()
    last_services: set[str] = set()
    last_actions: set[str] = set()
    last_group_missing: list[str] = []
    last_error = ''
    while time.monotonic() <= deadline:
        try:
            last_nodes = _cli_listing('ros2', 'node', 'list')
            last_topics = _cli_listing('ros2', 'topic', 'list')
            if expected_service_set:
                last_services = _cli_listing('ros2', 'service', 'list')
            if expected_action_set:
                last_actions = _cli_listing('ros2', 'action', 'list')
            groups_ready, last_group_missing = _groups_ready(expected_node_group_sets, last_nodes)
            if (
                expected_node_set.issubset(last_nodes)
                and expected_topic_set.issubset(last_topics)
                and expected_service_set.issubset(last_services)
                and expected_action_set.issubset(last_actions)
                and groups_ready
            ):
                print(f'[startup_barrier] {label}: ready')
                return 0
            missing_nodes = sorted(expected_node_set - last_nodes)
            missing_topics = sorted(expected_topic_set - last_topics)
            missing_services = sorted(expected_service_set - last_services)
            missing_actions = sorted(expected_action_set - last_actions)
            print(
                f'[startup_barrier] {label}: waiting nodes={missing_nodes} node_groups={last_group_missing} topics={missing_topics} services={missing_services} actions={missing_actions}',
                flush=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            last_error = str(exc)
            print(f'[startup_barrier] {label}: ros2 readiness probe failed: {exc}', file=sys.stderr, flush=True)
        time.sleep(max(0.05, float(poll_interval_sec)))
    missing_nodes = sorted(expected_node_set - last_nodes)
    missing_topics = sorted(expected_topic_set - last_topics)
    missing_services = sorted(expected_service_set - last_services)
    missing_actions = sorted(expected_action_set - last_actions)
    print(
        f'[startup_barrier] {label}: timeout waiting for nodes={missing_nodes} node_groups={last_group_missing} topics={missing_topics} services={missing_services} actions={missing_actions} error={last_error}',
        file=sys.stderr,
        flush=True,
    )
    return 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Wait for ROS startup dependencies.')
    parser.add_argument('--label', default='startup-barrier')
    parser.add_argument('--expected-node', action='append', default=[])
    parser.add_argument('--expected-node-group', action='append', default=[])
    parser.add_argument('--expected-topic', action='append', default=[])
    parser.add_argument('--expected-service', action='append', default=[])
    parser.add_argument('--expected-action', action='append', default=[])
    parser.add_argument('--timeout-sec', type=float, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument('--poll-interval-sec', type=float, default=DEFAULT_POLL_INTERVAL_SEC)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return wait_for_ros_graph(
        label=args.label,
        expected_nodes=args.expected_node,
        expected_topics=args.expected_topic,
        expected_services=args.expected_service,
        expected_actions=args.expected_action,
        expected_node_groups=args.expected_node_group,
        timeout_sec=args.timeout_sec,
        poll_interval_sec=args.poll_interval_sec,
    )


if __name__ == '__main__':
    raise SystemExit(main())
