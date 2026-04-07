from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'ros2_ws' / 'src'
for pkg in SRC.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_bridge.protocol_policy import ReplayOptions, filter_replay_payloads  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Replay JSONL payloads into robot_bridge TCP endpoint')
    parser.add_argument('path', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--delay', type=float, default=0.05, help='seconds between replayed payloads')
    parser.add_argument('--skip-faults', action='store_true')
    parser.add_argument('--skip-status', action='store_true')
    parser.add_argument('--skip-voice', action='store_true')
    return parser.parse_args()


def load_payloads(path: Path) -> list[dict]:
    payloads: list[dict] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payloads.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return payloads


def main() -> None:
    args = parse_args()
    options = ReplayOptions(include_faults=not args.skip_faults, include_status=not args.skip_status, include_voice=not args.skip_voice)
    payloads = filter_replay_payloads(load_payloads(args.path), options=options)
    with socket.create_connection((args.host, args.port), timeout=1.0) as sock:
        for payload in payloads:
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode('utf-8'))
            time.sleep(max(args.delay, 0.0))


if __name__ == '__main__':
    main()
