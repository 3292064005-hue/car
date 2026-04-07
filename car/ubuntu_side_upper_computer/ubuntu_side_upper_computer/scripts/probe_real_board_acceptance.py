#!/usr/bin/env python3
"""Probe live target evidence without overstating real-board verification."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_utils.verification_evidence import evidence_class_payload

DEFAULT_REQUIRED_NODES = ['robot_bridge_transport', 'robot_control', 'robot_decision']
DEFAULT_REQUIRED_TOPICS = ['/robot/chassis_state', '/robot/system_status', '/robot/mode_state']
DEFAULT_REQUIRED_SERVICES = ['/robot/set_mode', '/robot/reset_fault', '/robot/save_snapshot']
DEFAULT_REQUIRED_ACTIONS = ['/robot/actions/start_patrol', '/robot/actions/track_target', '/robot/actions/save_snapshot']
DEFAULT_ACTIVE_TOPICS = ['/robot/chassis_state', '/robot/system_status', '/robot/mode_state', '/robot/bridge/summary']


def _command_output(*args: str, timeout_sec: float = 10.0) -> dict[str, Any]:
    executable = shutil.which(args[0])
    if executable is None:
        return {'available': False, 'path': None, 'output': None, 'ok': False}
    try:
        completed = subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout_sec)
        output = (completed.stdout or completed.stderr).strip()
        return {'available': True, 'path': executable, 'output': output, 'ok': True}
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return {'available': True, 'path': executable, 'output': str(exc), 'ok': False}


def _probe_mjpeg(url: str, *, timeout_sec: float) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as response:  # noqa: S310
            status = getattr(response, 'status', None)
            content_type = response.headers.get('Content-Type') if getattr(response, 'headers', None) else None
            return {
                'reachable': True,
                'status': status,
                'contentType': content_type,
            }
    except Exception as exc:
        return {'reachable': False, 'error': str(exc)}


def _parse_lines(output: str | None) -> set[str]:
    return {line.strip() for line in str(output or '').splitlines() if line.strip()}


def _probe_topic_sample(topic: str, *, timeout_sec: float) -> dict[str, Any]:
    result = _command_output('ros2', 'topic', 'echo', topic, '--once', timeout_sec=max(1.0, timeout_sec))
    return {
        'topic': topic,
        'ok': bool(result.get('ok')) and bool(str(result.get('output') or '').strip()),
        'sample': str(result.get('output') or '')[:400],
        'details': result,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Probe observational live-runtime evidence.')
    parser.add_argument('--output', default='/tmp/real_board_acceptance.json')
    parser.add_argument('--mjpeg-url', default='http://127.0.0.1:8080/stream')
    parser.add_argument('--probe-timeout-sec', type=float, default=2.0)
    parser.add_argument('--required-node', action='append', default=[])
    parser.add_argument('--required-topic', action='append', default=[])
    parser.add_argument('--required-service', action='append', default=[])
    parser.add_argument('--required-action', action='append', default=[])
    parser.add_argument('--active-topic', action='append', default=[])
    parser.add_argument('--fail-on-probe-failure', action='store_true')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    node_info = _command_output('ros2', 'node', 'list')
    topic_info = _command_output('ros2', 'topic', 'list')
    service_info = _command_output('ros2', 'service', 'list')
    action_info = _command_output('ros2', 'action', 'list')
    required_nodes = args.required_node or list(DEFAULT_REQUIRED_NODES)
    required_topics = args.required_topic or list(DEFAULT_REQUIRED_TOPICS)
    required_services = args.required_service or list(DEFAULT_REQUIRED_SERVICES)
    required_actions = args.required_action or list(DEFAULT_REQUIRED_ACTIONS)
    active_topics = args.active_topic or list(DEFAULT_ACTIVE_TOPICS)
    node_lines = _parse_lines(node_info.get('output'))
    topic_lines = _parse_lines(topic_info.get('output'))
    service_lines = _parse_lines(service_info.get('output'))
    action_lines = _parse_lines(action_info.get('output'))
    missing_nodes = [name for name in required_nodes if not any(line.rstrip('/').endswith(name) for line in node_lines)]
    missing_topics = [name for name in required_topics if name not in topic_lines]
    missing_services = [name for name in required_services if name not in service_lines]
    missing_actions = [name for name in required_actions if name not in action_lines]
    live_topic_samples = [_probe_topic_sample(topic, timeout_sec=max(1.0, float(args.probe_timeout_sec))) for topic in active_topics]
    failed_live_topics = [item['topic'] for item in live_topic_samples if not item['ok']]
    mjpeg_probe = _probe_mjpeg(args.mjpeg_url, timeout_sec=max(0.2, float(args.probe_timeout_sec)))
    passed = (
        bool(node_info.get('available'))
        and bool(topic_info.get('available'))
        and bool(service_info.get('available'))
        and bool(action_info.get('available'))
        and not missing_nodes
        and not missing_topics
        and not missing_services
        and not missing_actions
        and not failed_live_topics
        and bool(mjpeg_probe.get('reachable', False))
    )
    payload = {
        'capturedAtUtc': datetime.now(timezone.utc).isoformat(),
        'requiredNodes': required_nodes,
        'requiredTopics': required_topics,
        'requiredServices': required_services,
        'requiredActions': required_actions,
        'activeTopics': active_topics,
        'missingNodes': missing_nodes,
        'missingTopics': missing_topics,
        'missingServices': missing_services,
        'missingActions': missing_actions,
        'failedLiveTopics': failed_live_topics,
        'liveTopicSamples': live_topic_samples,
        'mjpegProbe': mjpeg_probe,
        'ros2NodeList': node_info,
        'ros2TopicList': topic_info,
        'ros2ServiceList': service_info,
        'ros2ActionList': action_info,
        'evidenceClass': evidence_class_payload('hardware_probe_observational'),
        'claimBoundary': list(evidence_class_payload('hardware_probe_observational')['supportedClaims']),
        'passed': passed,
        'status': 'real_board_observational_probe_passed' if passed else 'real_board_probe_incomplete',
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    if args.fail_on_probe_failure and not passed:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
