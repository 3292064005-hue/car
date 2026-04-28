#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_utils.system_replay_bundle import (
    atomic_write_json,
    build_system_replay_bundle,
    build_system_replay_bundle_from_runtime_artifacts,
    validate_system_replay_bundle,
)


def _load_json(path_value: str, *, default, required: bool = False):
    normalized = str(path_value or '').strip()
    if not normalized:
        if required:
            raise FileNotFoundError('required JSON input path is empty')
        return default
    path = Path(normalized)
    if not path.is_file():
        if required:
            raise FileNotFoundError(f'required JSON input not found: {normalized}')
        return default
    payload = json.loads(path.read_text(encoding='utf-8'))
    return payload if payload is not None else default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build one system replay evidence bundle JSON file.')
    parser.add_argument('--source-name', default='robot-runtime')
    parser.add_argument('--session-metadata', default='')
    parser.add_argument('--runtime-dir', default='')
    parser.add_argument('--profile-name', default='mock')
    parser.add_argument('--provider-name', default='simple_nav_provider')
    parser.add_argument('--hardware-role', default='ros_projection_only')
    parser.add_argument('--evidence-class', default='host_harness_only')
    parser.add_argument('--topics', default='')
    parser.add_argument('--service-action-events', default='')
    parser.add_argument('--trace-correlation', default='')
    parser.add_argument('--logs', default='')
    parser.add_argument('--history', default='')
    parser.add_argument('--params', default='')
    parser.add_argument('--commands', default='')
    parser.add_argument('--inspector-trace', default='')
    parser.add_argument('--output', required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if str(args.runtime_dir or '').strip():
        bundle = build_system_replay_bundle_from_runtime_artifacts(
            args.runtime_dir,
            profile_name=args.profile_name,
            provider_name=args.provider_name,
            hardware_role=args.hardware_role,
            evidence_class=args.evidence_class,
        )
        bundle['sourceName'] = args.source_name
        bundle['exportedAt'] = datetime.now(timezone.utc).isoformat()
    else:
        bundle = build_system_replay_bundle(
            source_name=args.source_name,
            session_metadata=_load_json(args.session_metadata, default={}, required=True),
            topics=_load_json(args.topics, default=[]),
            service_action_events=_load_json(args.service_action_events, default=[]),
            trace_correlation=_load_json(args.trace_correlation, default=[]),
            logs=_load_json(args.logs, default=[]),
            history=_load_json(args.history, default={}),
            params=_load_json(args.params, default={}),
            commands=_load_json(args.commands, default=[]),
            inspector_trace=_load_json(args.inspector_trace, default=[]),
            exported_at=datetime.now(timezone.utc).isoformat(),
        )
    validation = validate_system_replay_bundle(bundle)
    if not validation.valid:
        raise SystemExit('invalid system replay bundle: ' + ','.join(validation.errors))
    atomic_write_json(args.output, bundle)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
