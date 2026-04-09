#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime_surface_inventory import runtime_signal_matrix_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render runtime signal producer/consumer matrix report')
    parser.add_argument('--output', default='-')
    parser.add_argument('--profile', default='mock')
    parser.add_argument('--config-path', default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = runtime_signal_matrix_payload(str(args.profile), config_path=(str(args.config_path) if args.config_path else None))
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output == '-':
        print(text)
    else:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
