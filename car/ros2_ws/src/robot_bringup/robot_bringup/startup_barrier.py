from __future__ import annotations

"""ROS startup barrier used by bringup launch sequencing.

The barrier intentionally uses the ``ros2`` CLI instead of in-process graph APIs so it
can run as a short-lived helper process from launch without importing the running
system's node implementations. Readiness can require a combination of ROS graph
presence (nodes/topics), semantic ready topics, and HTTP health probes when
operator-facing surfaces must be confirmed before launch proceeds.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Iterable


DEFAULT_TIMEOUT_SEC = 20.0
DEFAULT_POLL_INTERVAL_SEC = 0.25
DEFAULT_READY_TOPIC_ECHO_TIMEOUT_SEC = 3.0


def _normalize_entries(values: Iterable[str]) -> set[str]:
    normalized: set[str] = set()
    for item in values:
        raw = str(item or '').strip()
        if not raw:
            continue
        normalized.add(raw if raw.startswith('/') or '://' in raw else f'/{raw}')
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


def _ready_topic_probe(topic_name: str, *, timeout_sec: float = DEFAULT_READY_TOPIC_ECHO_TIMEOUT_SEC) -> tuple[bool, str]:
    """Probe one ready topic for at least one emitted message.

    Args:
        topic_name: ROS topic to probe.
        timeout_sec: Timeout for ``ros2 topic echo --once``.

    Returns:
        Tuple of ``(ready, detail)`` where ``detail`` is a diagnostic string.

    Raises:
        None. CLI failures are converted into ``False`` with diagnostic detail.

    Boundary behavior:
        A published payload that explicitly contains ``ready=false`` is treated
        as not ready. Any other non-empty payload counts as semantic readiness,
        which is stronger than mere topic advertisement.
    """
    try:
        completed = subprocess.run(
            ['ros2', 'topic', 'echo', topic_name, '--once'],
            check=True,
            capture_output=True,
            text=True,
            timeout=max(0.5, float(timeout_sec)),
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)
    payload = (completed.stdout or '').strip()
    if not payload:
        return False, 'empty topic echo payload'
    compact = payload.replace(' ', '').replace('\n', '')
    if '"ready":false' in compact or 'ready:false' in compact:
        return False, payload
    return True, payload


def _groups_ready(expected_groups: list[set[str]], observed_nodes: set[str]) -> tuple[bool, list[str]]:
    if not expected_groups:
        return True, []
    for group in expected_groups:
        if group.issubset(observed_nodes):
            return True, []
    missing_summary = [','.join(sorted(group - observed_nodes)) for group in expected_groups]
    return False, missing_summary


def _http_probe(url: str, *, ready_fields: list[str], timeout_sec: float = DEFAULT_READY_TOPIC_ECHO_TIMEOUT_SEC) -> tuple[bool, str]:
    """Probe one JSON health endpoint for truthy readiness fields.

    Args:
        url: HTTP endpoint to probe.
        ready_fields: JSON field names that must evaluate to ``True``.
        timeout_sec: Network timeout in seconds.

    Returns:
        ``(ready, detail)`` where ``detail`` contains the decoded payload or the
        failure reason.

    Raises:
        None. Network and decode failures are converted into ``False`` results.

    Boundary behavior:
        When the payload exposes ``ok`` but callers did not request it explicitly,
        ``ok`` is still enforced so transport availability cannot be mistaken for
        semantic readiness.
    """
    try:
        with urllib.request.urlopen(url, timeout=max(0.5, float(timeout_sec))) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return False, str(exc)
    if not isinstance(payload, dict):
        return False, 'health endpoint did not return a JSON object'
    fields = [field for field in ready_fields if field]
    if 'ok' in payload and 'ok' not in fields:
        fields.insert(0, 'ok')
    missing = [field for field in fields if not bool(payload.get(field))]
    if missing:
        return False, f'missing truthy health fields: {missing}'
    return True, json.dumps(payload, ensure_ascii=False)


def wait_for_ros_graph(
    *,
    label: str,
    expected_nodes: Iterable[str],
    expected_topics: Iterable[str],
    expected_services: Iterable[str],
    expected_actions: Iterable[str],
    expected_node_groups: Iterable[str],
    expected_ready_topics: Iterable[str] = (),
    expected_http_urls: Iterable[str] = (),
    expected_http_ready_fields: Iterable[str] = (),
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
) -> int:
    """Wait until one startup dependency set becomes ready.

    Args:
        label: Human-readable barrier label used in diagnostics.
        expected_nodes: Nodes that must appear in ``ros2 node list``.
        expected_topics: Topics that must appear in ``ros2 topic list``.
        expected_services: Services that must appear in ``ros2 service list``.
        expected_actions: Actions that must appear in ``ros2 action list``.
        expected_node_groups: Alternative node groups where any full group satisfies readiness.
        expected_ready_topics: Ready topics that must exist and emit a semantic ready payload.
        expected_http_urls: HTTP health endpoints that must return ready payloads.
        expected_http_ready_fields: Health payload fields that must evaluate truthy.
        timeout_sec: Total wait budget.
        poll_interval_sec: Delay between probes.

    Returns:
        ``0`` when ready, otherwise ``1`` after timeout.

    Raises:
        None. Probe failures are reported through the return code and stderr.
    """
    expected_node_set = _normalize_entries(expected_nodes)
    expected_topic_set = _normalize_entries(expected_topics)
    expected_ready_topic_set = _normalize_entries(expected_ready_topics)
    expected_service_set = _normalize_entries(expected_services)
    expected_action_set = _normalize_entries(expected_actions)
    expected_node_group_sets = _normalize_groups(expected_node_groups)
    expected_http_url_list = [str(item).strip() for item in expected_http_urls if str(item).strip()]
    expected_http_ready_field_list = [str(item).strip() for item in expected_http_ready_fields if str(item).strip()]
    deadline = time.monotonic() + max(0.1, float(timeout_sec))
    last_nodes: set[str] = set()
    last_topics: set[str] = set()
    last_services: set[str] = set()
    last_actions: set[str] = set()
    last_group_missing: list[str] = []
    last_ready_probe_detail: dict[str, str] = {}
    last_http_probe_detail: dict[str, str] = {}
    last_http_missing: list[str] = []
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
            ready_topics_visible = expected_ready_topic_set.issubset(last_topics)
            ready_topics_semantic = True
            last_ready_probe_detail = {}
            if ready_topics_visible and expected_ready_topic_set:
                for ready_topic in sorted(expected_ready_topic_set):
                    topic_ready, detail = _ready_topic_probe(ready_topic)
                    last_ready_probe_detail[ready_topic] = detail
                    if not topic_ready:
                        ready_topics_semantic = False
            http_ready = True
            last_http_probe_detail = {}
            last_http_missing = []
            for url in expected_http_url_list:
                endpoint_ready, detail = _http_probe(url, ready_fields=expected_http_ready_field_list)
                last_http_probe_detail[url] = detail
                if not endpoint_ready:
                    http_ready = False
                    last_http_missing.append(url)
            if (
                expected_node_set.issubset(last_nodes)
                and expected_topic_set.issubset(last_topics)
                and expected_service_set.issubset(last_services)
                and expected_action_set.issubset(last_actions)
                and ready_topics_visible
                and ready_topics_semantic
                and groups_ready
                and http_ready
            ):
                print(f'[startup_barrier] {label}: ready')
                return 0
            missing_nodes = sorted(expected_node_set - last_nodes)
            missing_topics = sorted(expected_topic_set - last_topics)
            missing_services = sorted(expected_service_set - last_services)
            missing_actions = sorted(expected_action_set - last_actions)
            missing_ready_topics = sorted(expected_ready_topic_set - last_topics)
            print(
                f'[startup_barrier] {label}: waiting nodes={missing_nodes} node_groups={last_group_missing} topics={missing_topics} ready_topics={missing_ready_topics} ready_topic_probe={last_ready_probe_detail} services={missing_services} actions={missing_actions} http_urls={last_http_missing} http_probe={last_http_probe_detail}',
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
    missing_ready_topics = sorted(expected_ready_topic_set - last_topics)
    print(
        f'[startup_barrier] {label}: timeout waiting for nodes={missing_nodes} node_groups={last_group_missing} topics={missing_topics} ready_topics={missing_ready_topics} ready_topic_probe={last_ready_probe_detail} services={missing_services} actions={missing_actions} http_urls={last_http_missing} http_probe={last_http_probe_detail} error={last_error}',
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
    parser.add_argument('--expected-ready-topic', action='append', default=[])
    parser.add_argument('--expected-http-url', action='append', default=[])
    parser.add_argument('--expected-http-ready-field', action='append', default=[])
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
        expected_ready_topics=args.expected_ready_topic,
        expected_http_urls=args.expected_http_url,
        expected_http_ready_fields=args.expected_http_ready_field,
        timeout_sec=args.timeout_sec,
        poll_interval_sec=args.poll_interval_sec,
    )


if __name__ == '__main__':
    raise SystemExit(main())
