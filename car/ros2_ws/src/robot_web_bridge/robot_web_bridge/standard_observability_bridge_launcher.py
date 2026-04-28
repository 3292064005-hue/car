from __future__ import annotations

"""External standard read-only observability bridge launcher."""

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from robot_web_bridge.standard_observability_contract import load_standard_observability_bridge_params, standard_observability_bridge_contract


def build_launch_command(*, bridge_family: str, listen_host: str, port: int, ws_path: str, command_override: Sequence[str], readonly_topics: Sequence[str] = (), upstream_url: str = 'ws://127.0.0.1:9001/ws') -> list[str]:
    contract = standard_observability_bridge_contract(enabled=True, bridge_family=bridge_family, listen_host=listen_host, port=port, ws_path=ws_path, command_override=command_override, readonly_topics=readonly_topics, upstream_url=upstream_url)
    command = [str(item) for item in contract['launchCommand']]
    if not command:
        raise ValueError(
            f"standard observability bridge runtime is policy-blocked for family {bridge_family!r}: "
            f"{contract.get('policyReason', 'missing_launch_command')}"
        )
    return command


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Launch the standard read-only observability bridge wrapper.')
    parser.add_argument('--family', required=True)
    parser.add_argument('--listen-host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--ws-path', default='/observability')
    parser.add_argument('--command-override', action='append', default=[])
    parser.add_argument('--readonly-topic', action='append', default=[])
    parser.add_argument('--upstream-url', default='ws://127.0.0.1:9001/ws')
    parser.add_argument('--config-root', default='')
    parser.add_argument('--dry-run', action='store_true')
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config_defaults = load_standard_observability_bridge_params(str(args.config_root)) if str(args.config_root or '').strip() else {}
    readonly_topics = tuple(args.readonly_topic) or tuple(config_defaults.get('readonly_topics', ()))
    upstream_url = str(config_defaults.get('upstream_url', args.upstream_url) or args.upstream_url)
    command_override = tuple(args.command_override) or tuple(config_defaults.get('command_override', ()))
    command = build_launch_command(bridge_family=str(args.family), listen_host=str(args.listen_host), port=int(args.port), ws_path=str(args.ws_path), command_override=command_override, readonly_topics=readonly_topics, upstream_url=upstream_url)
    os.environ.setdefault('INSPECTION_ROBOT_STANDARD_BRIDGE_HOST', str(args.listen_host))
    os.environ.setdefault('INSPECTION_ROBOT_STANDARD_BRIDGE_PORT', str(int(args.port)))
    os.environ.setdefault('INSPECTION_ROBOT_STANDARD_BRIDGE_WS_PATH', str(args.ws_path))
    if args.dry_run:
        print(' '.join(command))
        return 0
    os.execvp(command[0], command)
    raise AssertionError('os.execvp should not return')


if __name__ == '__main__':
    raise SystemExit(main())
